import re
import unicodedata
import uuid
from collections.abc import Collection
from datetime import datetime, timedelta, timezone
from typing import Any

from src import client, db
from src.models import (
    ConversationStage,
    Outcome,
    RiskFlag,
    TicketStatus,
)
from src.triage_rules import decide_triage, normalize_symptom


_OCR_CONFIDENCE_THRESHOLD = 0.80
_CONFIRMATION_WINDOW = timedelta(minutes=30)
_FINAL_STATUSES = frozenset(
    {TicketStatus.REMOTE_RESOLVED.value, TicketStatus.SUPPLIER.value}
)
_UNSUPPORTED_EQUIPMENT = frozenset({"chopper", "postmix"})

_RISK_PHRASES: dict[RiskFlag, tuple[str, ...]] = {
    RiskFlag.BURNING_SMELL: ("cheiro de queimado", "cheiro queimado"),
    RiskFlag.SPARK: ("faisca",),
    RiskFlag.DAMAGED_CABLE: ("cabo danificado",),
    RiskFlag.LEAK: ("vazamento",),
}


class InvalidTransitionError(ValueError):
    pass


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    unaccented = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", unaccented).split())


def _extract_risks(text: str) -> set[RiskFlag]:
    normalized = _normalize(text)
    return {
        risk
        for risk, phrases in _RISK_PHRASES.items()
        if any(phrase in normalized for phrase in phrases)
    }


def _has_unsupported_equipment(text: str) -> bool:
    tokens = set(_normalize(text).split())
    return bool(tokens.intersection(_UNSUPPORTED_EQUIPMENT))


def _is_negative(text: str) -> bool:
    normalized = _normalize(text)
    return normalized == "nao" or any(
        phrase in normalized for phrase in ("ainda nao", "nao resolveu", "continua")
    )


def _is_affirmative(text: str) -> bool:
    if _is_negative(text):
        return False
    return _normalize(text) in {
        "sim",
        "sim resolveu",
        "resolveu",
        "resolvido",
        "funcionou",
        "voltou ao normal",
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _confirmation_expired(ticket: dict[str, Any], now: datetime | None) -> bool:
    deadline_value = ticket["confirmation_deadline"]
    if deadline_value is None:
        return False
    current = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    return _as_utc(datetime.fromisoformat(str(deadline_value))) <= current


def _ticket_or_raise(ticket_id: str) -> dict[str, Any]:
    ticket = db.get_ticket(ticket_id)
    if ticket is None:
        raise KeyError(ticket_id)
    return ticket


def _ensure_active(ticket: dict[str, Any]) -> None:
    if (
        ticket["status"] in _FINAL_STATUSES
        or ticket["stage"] == ConversationStage.FINISHED.value
    ):
        raise InvalidTransitionError("O atendimento já foi finalizado.")


def require_identification(ticket_id: str) -> dict[str, Any]:
    ticket = _ticket_or_raise(ticket_id)
    _ensure_active(ticket)
    if (
        ticket["status"] != TicketStatus.TRIAGE.value
        or ticket["stage"] != ConversationStage.IDENTIFICATION.value
    ):
        raise InvalidTransitionError(
            "A identificação do equipamento não é aceita no estágio atual."
        )
    return ticket


def _append_assistant(
    ticket_id: str,
    message: str,
    kind: str = "text",
) -> dict[str, Any]:
    db.append_message(ticket_id, "assistant", message, kind)
    return _ticket_or_raise(ticket_id)


def _route_supplier(
    ticket_id: str,
    *,
    priority: str,
    reason: str,
    message: str,
) -> dict[str, Any]:
    db.set_ticket_state(
        ticket_id,
        TicketStatus.SUPPLIER,
        ConversationStage.FINISHED,
        priority=priority,
        reason=reason,
    )
    return _append_assistant(ticket_id, message, kind="routing")


def _route_critical_risk(ticket_id: str, source_text: str) -> dict[str, Any]:
    decision = decide_triage(normalize_symptom(source_text), _extract_risks(source_text))
    return _route_supplier(
        ticket_id,
        priority=decision.priority.value,
        reason=decision.reason,
        message=(
            "Identifiquei um sinal de risco. Não manipule nem abra o equipamento; "
            "o chamado foi encaminhado com urgência ao fornecedor."
        ),
    )


def _route_unsupported_equipment(ticket_id: str) -> dict[str, Any]:
    return _route_supplier(
        ticket_id,
        priority="normal",
        reason="equipamento_fora_do_escopo",
        message=(
            "Este atendimento atende apenas coolers e geladeiras. "
            "Para chopper ou postmix, acione o suporte responsável."
        ),
    )


def _agent_reply(ticket: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "nome_pdv": ticket["nome_pdv"],
        "assunto": ticket["assunto"],
        "stage": ticket["stage"],
        "messages": [
            {"role": message["role"], "content": message["content"]}
            for message in ticket["messages"]
        ],
    }
    return client.request_conversation_reply(payload)


def create_case(nome_pdv: str, assunto: str, descricao_base: str) -> dict[str, Any]:
    ticket_id = str(uuid.uuid4())
    db.create_ticket(ticket_id, nome_pdv, assunto, descricao_base)
    source_text = f"{assunto} {descricao_base}"
    if _extract_risks(source_text):
        return _route_critical_risk(ticket_id, source_text)
    if _has_unsupported_equipment(source_text):
        return _route_unsupported_equipment(ticket_id)
    opening = (
        f"Olá! Recebi um chamado do {nome_pdv} sobre {assunto}. "
        "Quero entender melhor o que está acontecendo e verificar se já consigo ajudar "
        "você agora. Você está próximo ao equipamento?"
    )
    return _append_assistant(ticket_id, opening, kind="opening")


def handle_text(
    ticket_id: str,
    text: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    ticket = _ticket_or_raise(ticket_id)
    _ensure_active(ticket)
    stage = ConversationStage(ticket["stage"])
    if stage is ConversationStage.CONFIRMATION and _confirmation_expired(ticket, now):
        return _route_supplier(
            ticket_id,
            priority=str(ticket["priority"]),
            reason="sem_confirmacao_pdv",
            message=(
                "Como não houve confirmação do PDV em 30 minutos, "
                "o chamado foi encaminhado ao fornecedor."
            ),
        )
    db.append_message(ticket_id, "user", text)

    risks = _extract_risks(text)
    if risks:
        return _route_critical_risk(ticket_id, text)
    if _has_unsupported_equipment(text):
        return _route_unsupported_equipment(ticket_id)

    if stage is ConversationStage.PROXIMITY:
        if _is_negative(text):
            return _append_assistant(
                ticket_id,
                "Tudo bem. O atendimento pode ser retomado quando o PDV estiver junto ao cooler.",
                kind="conversation",
            )
        if _is_affirmative(text):
            db.set_ticket_state(
                ticket_id,
                TicketStatus.TRIAGE,
                ConversationStage.IDENTIFICATION,
            )
            return _append_assistant(
                ticket_id,
                "Envie uma foto da etiqueta do cooler ou informe o modelo e o número de série.",
                kind="identification",
            )

    elif stage is ConversationStage.CONFIRMATION:
        if _is_negative(text):
            return _route_supplier(
                ticket_id,
                priority="normal",
                reason="problema_persistiu_apos_checklist",
                message="Como o problema continua, encaminhei o chamado ao fornecedor.",
            )
        if _is_affirmative(text):
            db.set_ticket_state(
                ticket_id,
                TicketStatus.REMOTE_RESOLVED,
                ConversationStage.FINISHED,
                reason="confirmacao_positiva_pdv",
            )
            return _append_assistant(
                ticket_id,
                "Ótimo! Registrei sua confirmação e encerrei o chamado como resolvido remotamente.",
                kind="resolution",
            )

    reply = _agent_reply(_ticket_or_raise(ticket_id))
    interpreted_risks = _extract_risks(" ".join(reply.get("risks", [])))
    if interpreted_risks:
        decision = decide_triage(normalize_symptom(reply.get("symptom", "")), interpreted_risks)
        return _route_supplier(
            ticket_id,
            priority=decision.priority.value,
            reason=decision.reason,
            message=(
                "Identifiquei um sinal de risco. Não manipule nem abra o equipamento; "
                "o chamado foi encaminhado com urgência ao fornecedor."
            ),
        )
    return _append_assistant(ticket_id, reply["message"], kind="conversation")


def _diagnose(ticket_id: str) -> dict[str, Any]:
    ticket = _ticket_or_raise(ticket_id)
    source_text = " ".join(
        [
            str(ticket["assunto"]),
            str(ticket["descricao_base"]),
            *(message["content"] for message in ticket["messages"] if message["role"] == "user"),
        ]
    )
    decision = decide_triage(normalize_symptom(source_text), _extract_risks(source_text))

    if decision.outcome is Outcome.SUPPLIER:
        urgent = decision.priority.value == "urgente"
        return _route_supplier(
            ticket_id,
            priority=decision.priority.value,
            reason=decision.reason,
            message=(
                "Não manipule nem abra o equipamento. Encaminhei o chamado com urgência ao fornecedor."
                if urgent
                else "Este caso requer atendimento técnico e foi encaminhado ao fornecedor."
            ),
        )

    deadline = datetime.now(timezone.utc) + _CONFIRMATION_WINDOW
    db.set_ticket_state(
        ticket_id,
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        deadline,
        priority=decision.priority.value,
        reason=decision.reason,
    )
    checklist = " ".join(
        f"{index}. {item}" for index, item in enumerate(decision.checklist, start=1)
    )
    return _append_assistant(
        ticket_id,
        f"Siga estas verificações seguras: {checklist} O cooler voltou a funcionar corretamente?",
        kind="checklist",
    )


def handle_label(
    ticket_id: str,
    label: dict[str, Any],
    image_name: str | None,
) -> dict[str, Any]:
    require_identification(ticket_id)
    modelo = str(label.get("modelo", ""))
    numero_serie = str(label.get("numero_serie", ""))
    confianca = float(label.get("confianca", 0.0))
    db.set_equipment(ticket_id, modelo, numero_serie, confianca, image_name)

    if confianca < _OCR_CONFIDENCE_THRESHOLD or not numero_serie.strip():
        db.set_ticket_state(
            ticket_id,
            TicketStatus.TRIAGE,
            ConversationStage.IDENTIFICATION,
            reason="identificacao_manual_necessaria",
        )
        return _append_assistant(
            ticket_id,
            "Não consegui confirmar a etiqueta com segurança. Informe o serial manualmente.",
            kind="identification",
        )

    db.append_message(
        ticket_id,
        "assistant",
        f"Identifiquei o modelo {modelo} e o serial {numero_serie}.",
        "identification",
    )
    return _diagnose(ticket_id)


def handle_serial(ticket_id: str, modelo: str, numero_serie: str) -> dict[str, Any]:
    require_identification(ticket_id)
    if not numero_serie.strip():
        raise ValueError("O número de série é obrigatório.")
    db.set_equipment(ticket_id, modelo, numero_serie, 1.0, None)
    db.append_message(
        ticket_id,
        "assistant",
        f"Registrei o modelo {modelo} e o serial {numero_serie}.",
        "identification",
    )
    return _diagnose(ticket_id)


def expire_confirmations(
    now: datetime | None = None,
    ticket_ids: Collection[str] | None = None,
) -> list[str]:
    expired = db.list_expired_confirmations(now, ticket_ids)
    expired_ids = []
    for ticket in expired:
        ticket_id = str(ticket["id"])
        _route_supplier(
            ticket_id,
            priority=str(ticket["priority"]),
            reason="sem_confirmacao_pdv",
            message=(
                "Como não houve confirmação do PDV em 30 minutos, "
                "o chamado foi encaminhado ao fornecedor."
            ),
        )
        expired_ids.append(ticket_id)
    return expired_ids


def supplier_summary(ticket_id: str) -> dict[str, object]:
    ticket = _ticket_or_raise(ticket_id)
    equipment = ticket["equipment"]
    if equipment is None:
        raise ValueError("O equipamento do chamado não foi identificado.")
    return {
        "ticket_id": ticket_id,
        "nome_pdv": ticket["nome_pdv"],
        "assunto": ticket["assunto"],
        "modelo": equipment["modelo"],
        "numero_serie": equipment["numero_serie"],
        "prioridade": ticket["priority"],
        "motivo": ticket["outcome_reason"],
        "acoes_tentadas": [
            message["content"]
            for message in ticket["messages"]
            if message["role"] == "assistant"
            and message["kind"] == "checklist"
        ],
    }
