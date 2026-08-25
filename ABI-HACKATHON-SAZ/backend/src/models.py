from enum import Enum
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TicketStatus(str, Enum):
    TRIAGE = "em_triagem"
    WAITING_CONFIRMATION = "aguardando_confirmacao"
    REMOTE_RESOLVED = "resolvido_remotamente"
    SUPPLIER = "encaminhado_fornecedor"


class EquipmentType(str, Enum):
    COOLER = "cooler"
    GELADEIRA = "geladeira"


class ConversationStage(str, Enum):
    PROXIMITY = "aguardando_proximidade"
    IDENTIFICATION = "aguardando_identificacao"
    EQUIPMENT_CONFIRMATION = "aguardando_confirmacao_equipamento"
    DIAGNOSIS = "diagnostico"
    CONFIRMATION = "aguardando_confirmacao"
    FINISHED = "finalizado"


class Symptom(str, Enum):
    FREEZING_DRINKS = "congela_bebidas"
    DOOR_NOT_CLOSING = "porta_nao_fecha"
    NOT_COOLING = "nao_gela"
    NOT_POWERING_ON = "nao_liga"
    ABNORMAL_NOISE = "ruido_anormal"
    UNKNOWN = "desconhecido"


class RiskFlag(str, Enum):
    BURNING_SMELL = "cheiro_queimado"
    SPARK = "faisca"
    DAMAGED_CABLE = "cabo_danificado"
    LEAK = "vazamento"


class Outcome(str, Enum):
    REMOTE_CHECKLIST = "checklist_remoto"
    SUPPLIER = "encaminhado_fornecedor"


class Priority(str, Enum):
    NORMAL = "normal"
    URGENT = "urgente"


class EvidenceType(str, Enum):
    INITIAL_DESCRIPTION = "descricao_inicial"
    PDV_REPORT = "relato_pdv"
    LABEL_PHOTO = "foto_etiqueta"


class SupplierEvidence(BaseModel):
    tipo: EvidenceType
    descricao: str


class SupplierEquipment(BaseModel):
    tipo: EquipmentType
    modelo: str
    numero_serie: str
    confianca: float
    foto_etiqueta: str | None = None


class SupplierSummary(BaseModel):
    ticket_id: str
    nome_pdv: str
    assunto: str
    equipamento: SupplierEquipment | None = None
    evidencias: list[SupplierEvidence] = Field(default_factory=list)
    acoes_tentadas: list[str] = Field(default_factory=list)
    prioridade: Priority
    motivo: str


class TicketMessage(BaseModel):
    role: str
    content: str
    kind: str
    created_at: str


class TicketEquipment(BaseModel):
    modelo: str
    numero_serie: str
    confianca: float
    image_name: str | None = None


class TicketResponse(BaseModel):
    id: str
    nome_pdv: str
    assunto: str
    descricao_base: str
    equipment_type: EquipmentType
    status: TicketStatus
    stage: ConversationStage
    confirmation_deadline: str | None = None
    priority: Priority
    outcome_reason: str
    created_at: str
    updated_at: str
    equipment: TicketEquipment | None = None
    messages: list[TicketMessage] = Field(default_factory=list)
    supplier_summary: SupplierSummary | None = None


class AgentReplyKey(str, Enum):
    CONFIRM_PROXIMITY = "confirmar_proximidade"
    REQUEST_IDENTIFICATION = "solicitar_identificacao"
    CONFIRM_EQUIPMENT = "confirmar_equipamento"
    CONFIRM_RESOLUTION = "confirmar_resolucao"
    DESCRIBE_SYMPTOM = "descrever_sintoma"
    OUT_OF_SCOPE = "equipamento_fora_do_escopo"


class AgentConversationReply(BaseModel):
    # Unknown upstream fields are intentionally discarded. In particular, a
    # legacy or hostile `message` value must never become PDV-facing content.
    model_config = ConfigDict(extra="ignore")

    reply_key: AgentReplyKey
    risks: list[RiskFlag] = Field(default_factory=list)
    symptom: Symptom = Symptom.UNKNOWN


class TriageDecision(BaseModel):
    outcome: Outcome
    priority: Priority = Priority.NORMAL
    checklist: list[str] = Field(default_factory=list)
    reason: str


class TicketEventCategory(str, Enum):
    TICKET_CREATED = "ticket_created"
    SCOPE_VALIDATED = "scope_validated"
    RISK_EVALUATED = "risk_evaluated"
    STAGE_CHANGED = "stage_changed"
    AGENT_REQUESTED = "agent_requested"
    AGENT_INTERPRETED = "agent_interpreted"
    OCR_COMPLETED = "ocr_completed"
    EQUIPMENT_CONFIRMED = "equipment_confirmed"
    TRIAGE_DECISION = "triage_decision"
    CHECKLIST_SENT = "checklist_sent"
    CONFIRMATION_WAITING = "confirmation_waiting"
    TICKET_RESOLVED = "ticket_resolved"
    SUPPLIER_ROUTED = "supplier_routed"
    CONFIRMATION_EXPIRED = "confirmation_expired"


class TicketEventState(str, Enum):
    COMPLETED = "completed"
    ACTIVE = "active"
    WAITING = "waiting"
    WARNING = "warning"
    FAILED = "failed"


TicketEventMetadataValue: TypeAlias = str | int | float | bool | None | list[str]


class TicketEventWrite(BaseModel):
    category: TicketEventCategory
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    state: TicketEventState
    metadata: dict[str, TicketEventMetadataValue] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(
        cls,
        metadata: dict[str, TicketEventMetadataValue],
    ) -> dict[str, TicketEventMetadataValue]:
        forbidden_categories = (
            "prompt",
            "credential",
            "password",
            "secret",
            "apikey",
            "token",
            "authorization",
            "message",
            "rawresponse",
            "modelresponse",
            "response",
            "stacktrace",
            "traceback",
            "errortrace",
            "chainofthought",
            "thought",
            "reasoning",
            "cot",
        )
        normalized_keys = (
            "".join(character for character in key.casefold() if character.isalnum())
            for key in metadata
        )
        if any(
            category in normalized_key
            for normalized_key in normalized_keys
            for category in forbidden_categories
        ):
            raise ValueError("Metadado sensível não é permitido em eventos.")
        if any(
            isinstance(value, list) and not all(isinstance(item, str) for item in value)
            for value in metadata.values()
        ):
            raise ValueError("Listas de metadados aceitam somente strings.")
        return metadata


class TicketEvent(TicketEventWrite):
    id: int
    ticket_id: str
    created_at: str


class TicketEventsResponse(BaseModel):
    items: list[TicketEvent]
    last_id: int
    terminal: bool
