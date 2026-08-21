from enum import Enum

from pydantic import BaseModel, Field


class TicketStatus(str, Enum):
    TRIAGE = "em_triagem"
    WAITING_CONFIRMATION = "aguardando_confirmacao"
    REMOTE_RESOLVED = "resolvido_remotamente"
    SUPPLIER = "encaminhado_fornecedor"


class ConversationStage(str, Enum):
    PROXIMITY = "aguardando_proximidade"
    IDENTIFICATION = "aguardando_identificacao"
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


class TriageDecision(BaseModel):
    outcome: Outcome
    priority: Priority = Priority.NORMAL
    checklist: list[str] = Field(default_factory=list)
    reason: str
