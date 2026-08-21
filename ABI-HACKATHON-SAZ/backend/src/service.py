import re
import unicodedata
import uuid
from collections.abc import Collection
from datetime import datetime, timedelta, timezone
from typing import Any

from src import client, db
from src.models import (
    AgentConversationReply,
    AgentReplyKey,
    ConversationStage,
    EvidenceType,
    EquipmentType,
    Outcome,
    Priority,
    RiskFlag,
    SupplierEquipment,
    SupplierEvidence,
    SupplierSummary,
    TicketStatus,
)
from src.triage_rules import decide_triage, normalize_symptom


_OCR_CONFIDENCE_THRESHOLD = 0.80
_CONFIRMATION_WINDOW = timedelta(minutes=30)
_FINAL_STATUSES = frozenset(
    {TicketStatus.REMOTE_RESOLVED.value, TicketStatus.SUPPLIER.value}
)
_UNSUPPORTED_EQUIPMENT_PHRASES = (
    "ar condicionado",
    "arcondicionado",
    "chopper",
    "postmix",
    "post mix",
)
_SUPPORTED_EQUIPMENT_PHRASES: dict[EquipmentType, tuple[str, ...]] = {
    EquipmentType.COOLER: ("cooler", "coolers"),
    EquipmentType.GELADEIRA: ("geladeira", "geladeiras"),
}

_RISK_PHRASES: dict[RiskFlag, tuple[str, ...]] = {
    RiskFlag.BURNING_SMELL: (
        "cheiro de queimado",
        "cheiro a queimado",
        "cheiro queimado",
    ),
    RiskFlag.SPARK: ("faisca", "faiscas"),
    RiskFlag.DAMAGED_CABLE: ("cabo danificado", "cabo esta danificado"),
    RiskFlag.LEAK: ("vazamento", "vazando", "esta vazando"),
}

_AGENT_REPLY_TEMPLATES: dict[
    ConversationStage, tuple[AgentReplyKey, str]
] = {
    ConversationStage.PROXIMITY: (
        AgentReplyKey.CONFIRM_PROXIMITY,
        "Para continuar, confirme: você está próximo ao equipamento?",
    ),
    ConversationStage.IDENTIFICATION: (
        AgentReplyKey.REQUEST_IDENTIFICATION,
        "Envie uma foto da etiqueta ou informe o modelo e o número de série.",
    ),
    ConversationStage.EQUIPMENT_CONFIRMATION: (
        AgentReplyKey.CONFIRM_EQUIPMENT,
        "Confira o modelo e o número de série exibidos. Os dados estão corretos?",
    ),
    ConversationStage.DIAGNOSIS: (
        AgentReplyKey.DESCRIBE_SYMPTOM,
        "Descreva o que está acontecendo com o equipamento.",
    ),
    ConversationStage.CONFIRMATION: (
        AgentReplyKey.CONFIRM_RESOLUTION,
        "Quando terminar as verificações, confirme se o equipamento voltou a "
        "funcionar corretamente.",
    ),
}


class InvalidTransitionError(ValueError):
    pass


class AgentResponseError(ValueError):
    pass


class EquipmentScopeError(ValueError):
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


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {normalized_text} "


def _validate_equipment_scope(
    equipment_type: EquipmentType | str,
    *texts: str,
) -> EquipmentType:
    try:
        expected_type = EquipmentType(equipment_type)
    except ValueError as exc:
        raise EquipmentScopeError(
            "O tipo de equipamento deve ser cooler ou geladeira."
        ) from exc

    normalized = _normalize(" ".join(texts))
    if any(
        _contains_phrase(normalized, phrase)
        for phrase in _UNSUPPORTED_EQUIPMENT_PHRASES
    ):
        raise EquipmentScopeError(
            "O equipamento informado está fora do escopo; use apenas cooler ou geladeira."
        )

    mentioned_types = {
        candidate
        for candidate, phrases in _SUPPORTED_EQUIPMENT_PHRASES.items()
        if any(_contains_phrase(normalized, phrase) for phrase in phrases)
    }
    if any(candidate is not expected_type for candidate in mentioned_types):
        raise EquipmentScopeError(
            "O equipamento mencionado contradiz o tipo informado no chamado."
        )
    return expected_type


def _is_negative(text: str) -> bool:
    normalized = _normalize(text)
    return normalized == "nao" or any(
        phrase in normalized
        for phrase in (
            "ainda nao",
            "nao resolveu",
            "continua",
            "nao os dados",
            "dados errados",
            "nao estao corretos",
            "nao estou proximo",
            "nao estou perto",
        )
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
        "sim os dados estao corretos",
        "dados corretos",
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


def _await_equipment_confirmation(ticket_id: str) -> dict[str, Any]:
    db.set_ticket_state(
        ticket_id,
        TicketStatus.TRIAGE,
        ConversationStage.EQUIPMENT_CONFIRMATION,
        reason="identificacao_aguardando_confirmacao",
    )
    return _append_assistant(
        ticket_id,
        "Confira o modelo e o número de série exibidos. Os dados estão corretos?",
        kind="identification",
    )


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


def _agent_reply(ticket: dict[str, Any]) -> AgentConversationReply:
    payload = {
        "nome_pdv": ticket["nome_pdv"],
        "assunto": ticket["assunto"],
        "stage": ticket["stage"],
        "messages": [
            {"role": message["role"], "content": message["content"]}
            for message in ticket["messages"]
        ],
    }
    raw_reply = client.request_conversation_reply(payload)
    try:
        return AgentConversationReply.model_validate(raw_reply)
    except ValueError as exc:
        raise AgentResponseError(
            "O agente retornou uma resposta estruturada inválida."
        ) from exc


def _render_agent_reply(
    stage: ConversationStage,
    reply_key: AgentReplyKey,
) -> str:
    expected = _AGENT_REPLY_TEMPLATES.get(stage)
    if expected is None or reply_key is not expected[0]:
        raise AgentResponseError(
            "O agente retornou uma intenção incompatível com a etapa atual."
        )
    return expected[1]


def create_case(
    nome_pdv: str,
    assunto: str,
    descricao_base: str,
    equipment_type: EquipmentType = EquipmentType.COOLER,
) -> dict[str, Any]:
    ticket_id = str(uuid.uuid4())
    source_text = f"{assunto} {descricao_base}"
    risks = _extract_risks(source_text)
    validated_type = EquipmentType(equipment_type)
    if not risks:
        validated_type = _validate_equipment_scope(validated_type, source_text)
    db.create_ticket(
        ticket_id,
        nome_pdv,
        assunto,
        descricao_base,
        validated_type,
    )
    if risks:
        return _route_critical_risk(ticket_id, source_text)
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
    risks = _extract_risks(text)
    if risks:
        db.append_message(ticket_id, "user", text)
        return _route_critical_risk(ticket_id, text)
    _validate_equipment_scope(str(ticket["equipment_type"]), text)
    db.append_message(ticket_id, "user", text)

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

    elif stage is ConversationStage.EQUIPMENT_CONFIRMATION:
        if _is_negative(text):
            db.set_ticket_state(
                ticket_id,
                TicketStatus.TRIAGE,
                ConversationStage.IDENTIFICATION,
                reason="correcao_identificacao_necessaria",
            )
            return _append_assistant(
                ticket_id,
                "Certo. Corrija o modelo e o número de série antes de continuar.",
                kind="identification",
            )
        if _is_affirmative(text):
            return _diagnose(ticket_id)

    reply = _agent_reply(_ticket_or_raise(ticket_id))
    interpreted_risks = set(reply.risks)
    if interpreted_risks:
        decision = decide_triage(reply.symptom, interpreted_risks)
        return _route_supplier(
            ticket_id,
            priority=decision.priority.value,
            reason=decision.reason,
            message=(
                "Identifiquei um sinal de risco. Não manipule nem abra o equipamento; "
                "o chamado foi encaminhado com urgência ao fornecedor."
            ),
        )
    return _append_assistant(
        ticket_id,
        _render_agent_reply(stage, reply.reply_key),
        kind="conversation",
    )


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
    db.record_checklist_actions(ticket_id, decision.checklist)
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
    ticket = require_identification(ticket_id)
    modelo = str(label.get("modelo", ""))
    numero_serie = str(label.get("numero_serie", ""))
    confianca = float(label.get("confianca", 0.0))
    _validate_equipment_scope(str(ticket["equipment_type"]), modelo)
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

    return _await_equipment_confirmation(ticket_id)


def handle_serial(ticket_id: str, modelo: str, numero_serie: str) -> dict[str, Any]:
    ticket = require_identification(ticket_id)
    if not numero_serie.strip():
        raise ValueError("O número de série é obrigatório.")
    _validate_equipment_scope(str(ticket["equipment_type"]), modelo)
    current_equipment = ticket["equipment"]
    image_name = (
        current_equipment["image_name"]
        if current_equipment is not None
        else None
    )
    db.set_equipment(ticket_id, modelo, numero_serie, 1.0, image_name)
    return _await_equipment_confirmation(ticket_id)


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


def supplier_summary(ticket_id: str) -> SupplierSummary:
    ticket = _ticket_or_raise(ticket_id)
    equipment = ticket["equipment"]
    description = str(ticket["descricao_base"]).strip() or str(ticket["assunto"])
    evidence = [
        SupplierEvidence(
            tipo=EvidenceType.INITIAL_DESCRIPTION,
            descricao=description,
        )
    ]
    control_replies = {
        "sim",
        "nao",
        "sim os dados estao corretos",
        "dados corretos",
        "nao corrigir",
    }
    evidence.extend(
        SupplierEvidence(
            tipo=EvidenceType.PDV_REPORT,
            descricao=str(message["content"]),
        )
        for message in ticket["messages"]
        if message["role"] == "user"
        and _normalize(str(message["content"])) not in control_replies
    )
    supplier_equipment = None
    if equipment is not None:
        image_name = equipment["image_name"]
        supplier_equipment = SupplierEquipment(
            tipo=EquipmentType(str(ticket["equipment_type"])),
            modelo=str(equipment["modelo"]),
            numero_serie=str(equipment["numero_serie"]),
            confianca=float(equipment["confianca"]),
            foto_etiqueta=str(image_name) if image_name is not None else None,
        )
        if image_name:
            evidence.append(
                SupplierEvidence(
                    tipo=EvidenceType.LABEL_PHOTO,
                    descricao=str(image_name),
                )
            )

    actions = [str(action) for action in ticket.get("checklist_actions", [])]
    if not actions:
        # Preserve useful evidence for tickets created before the structured
        # checklist-actions migration without changing their stored history.
        actions = [
            str(message["content"])
            for message in ticket["messages"]
            if message["role"] == "assistant" and message["kind"] == "checklist"
        ]

    return SupplierSummary(
        ticket_id=ticket_id,
        nome_pdv=str(ticket["nome_pdv"]),
        assunto=str(ticket["assunto"]),
        equipamento=supplier_equipment,
        evidencias=evidence,
        acoes_tentadas=actions,
        prioridade=Priority(str(ticket["priority"])),
        motivo=str(ticket["outcome_reason"]),
    )
