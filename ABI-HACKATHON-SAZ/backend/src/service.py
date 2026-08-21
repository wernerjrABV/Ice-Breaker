import unicodedata
import uuid
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

_RISK_PHRASES: dict[RiskFlag, tuple[str, ...]] = {
    RiskFlag.BURNING_SMELL: ("cheiro de queimado", "cheiro queimado"),
    RiskFlag.SPARK: ("faisca",),
    RiskFlag.DAMAGED_CABLE: ("cabo danificado",),
    RiskFlag.LEAK: ("vazamento",),
}


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    unaccented = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(unaccented.replace("_", " ").split())


def _extract_risks(text: str) -> set[RiskFlag]:
    normalized = _normalize(text)
    return {
        risk
        for risk, phrases in _RISK_PHRASES.items()
        if any(phrase in normalized for phrase in phrases)
    }


def _is_negative(text: str) -> bool:
    normalized = _normalize(text)
    return any(
        phrase in normalized
        for phrase in ("nao", "não", "ainda nao", "nao resolveu", "continua")
    )


def _is_affirmative(text: str) -> bool:
    if _is_negative(text):
        return False
    tokens = set(_normalize(text).replace(",", " ").split())
    return bool(tokens.intersection({"sim", "resolvido", "resolveu", "funcionou", "estou"}))


def _ticket_or_raise(ticket_id: str) -> dict[str, Any]:
    ticket = db.get_ticket(ticket_id)
    if ticket is None:
        raise KeyError(ticket_id)
    return ticket


def _append_assistant(ticket_id: str, message: str) -> dict[str, Any]:
    db.append_message(ticket_id, "assistant", message)
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
    return _append_assistant(ticket_id, message)


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
    opening = (
        f"Olá! Recebi um chamado do {nome_pdv} sobre {assunto}. "
        "Quero entender melhor o que está acontecendo e verificar se já consigo ajudar "
        "você agora. Você está próximo ao equipamento?"
    )
    return _append_assistant(ticket_id, opening)


def handle_text(ticket_id: str, text: str) -> dict[str, Any]:
    ticket = _ticket_or_raise(ticket_id)
    db.append_message(ticket_id, "user", text)

    risks = _extract_risks(text)
    if risks:
        decision = decide_triage(normalize_symptom(text), risks)
        return _route_supplier(
            ticket_id,
            priority=decision.priority.value,
            reason=decision.reason,
            message=(
                "Identifiquei um sinal de risco. Não manipule nem abra o equipamento; "
                "o chamado foi encaminhado com urgência ao fornecedor."
            ),
        )

    stage = ConversationStage(ticket["stage"])
    if stage is ConversationStage.PROXIMITY:
        if _is_negative(text):
            return _append_assistant(
                ticket_id,
                "Tudo bem. O atendimento pode ser retomado quando o PDV estiver junto ao cooler.",
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
            )

    elif stage is ConversationStage.FINISHED:
        return _append_assistant(ticket_id, "Este atendimento já foi finalizado.")

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
    return _append_assistant(ticket_id, reply["message"])


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
    )


def handle_label(
    ticket_id: str,
    label: dict[str, Any],
    image_name: str | None,
) -> dict[str, Any]:
    _ticket_or_raise(ticket_id)
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
        )

    db.append_message(
        ticket_id,
        "assistant",
        f"Identifiquei o modelo {modelo} e o serial {numero_serie}.",
    )
    return _diagnose(ticket_id)


def handle_serial(ticket_id: str, modelo: str, numero_serie: str) -> dict[str, Any]:
    _ticket_or_raise(ticket_id)
    if not numero_serie.strip():
        raise ValueError("O número de série é obrigatório.")
    db.set_equipment(ticket_id, modelo, numero_serie, 1.0, None)
    db.append_message(
        ticket_id,
        "assistant",
        f"Registrei o modelo {modelo} e o serial {numero_serie}.",
    )
    return _diagnose(ticket_id)


def expire_confirmations(now: datetime | None = None) -> list[dict[str, Any]]:
    expired = db.list_expired_confirmations(now)
    updated = []
    for ticket in expired:
        updated.append(
            _route_supplier(
                str(ticket["id"]),
                priority=str(ticket["priority"]),
                reason="sem_confirmacao_pdv",
                message=(
                    "Como não houve confirmação do PDV em 30 minutos, "
                    "o chamado foi encaminhado ao fornecedor."
                ),
            )
        )
    return updated
