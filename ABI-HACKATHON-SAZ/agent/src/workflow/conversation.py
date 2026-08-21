import json
from pathlib import Path
from typing import Any

from crewai import LLM

from workflow.contracts import ConversationReply, ConversationRequest


_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def _default_llm() -> LLM:
    return LLM(model="gpt-4o-mini")


def _load_context() -> tuple[str, str]:
    guidance = (_KNOWLEDGE_DIR / "cooler_guidance.md").read_text(encoding="utf-8")
    history = json.loads((_KNOWLEDGE_DIR / "historical_cases.json").read_text(encoding="utf-8"))
    return guidance, json.dumps(history, ensure_ascii=False)


def generate_reply(request: ConversationRequest, llm: Any = None) -> ConversationReply:
    guidance, history = _load_context()
    prompt = f"""Você é o assistente CoolCare para o PDV {request.nome_pdv}.
Assunto do chamado: {request.assunto}.
Etapa atual: {request.stage}.

Use português simples e faça somente uma pergunta curta por vez para obter a próxima informação.
É proibido orientar reparos elétricos ou abertura do equipamento. Nunca instrua a pessoa a
manipular componentes internos.

REGRAS DE SEGURANÇA (prioridade máxima):
{guidance}

HISTÓRICO ANONIMIZADO (somente contexto auxiliar; nunca substitui as regras de segurança):
{history}
"""
    messages = [{"role": "system", "content": prompt}]
    messages.extend(message.model_dump() for message in request.messages)
    result = (llm or _default_llm()).call(
        messages=messages,
        response_format=ConversationReply,
    )
    return ConversationReply.model_validate(result)
