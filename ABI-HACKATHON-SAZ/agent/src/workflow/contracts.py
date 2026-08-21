from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReplyKey = Literal[
    "confirmar_proximidade",
    "solicitar_identificacao",
    "confirmar_equipamento",
    "confirmar_resolucao",
    "descrever_sintoma",
    "equipamento_fora_do_escopo",
]
RiskKey = Literal[
    "cheiro_queimado",
    "faisca",
    "cabo_danificado",
    "vazamento",
    "equipamento_fora_do_escopo",
]
SymptomKey = Literal[
    "congela_bebidas",
    "porta_nao_fecha",
    "nao_gela",
    "nao_liga",
    "ruido_anormal",
    "desconhecido",
]


class EquipmentLabel(BaseModel):
    modelo: str = ""
    numero_serie: str = ""
    confianca: float = Field(ge=0, le=1)


class LabelReadRequest(BaseModel):
    image_data_url: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConversationRequest(BaseModel):
    nome_pdv: str
    assunto: str
    stage: str
    messages: list[ChatMessage]


class ConversationReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply_key: ReplyKey
    risks: list[RiskKey] = Field(default_factory=list)
    symptom: SymptomKey = "desconhecido"
