from typing import Literal

from pydantic import BaseModel, Field


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
    message: str
    risks: list[str] = Field(default_factory=list)
    symptom: str = "desconhecido"
