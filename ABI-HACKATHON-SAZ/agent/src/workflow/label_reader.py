import os
from typing import Any

from crewai import LLM

from workflow.contracts import EquipmentLabel


def _default_llm() -> LLM:
    model = os.getenv("OPENAI_MODEL", "").strip() or "openai/gpt-4o-mini"
    return LLM(model=model)


def read_label(image_data_url: str, llm: Any = None) -> EquipmentLabel:
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Leia a etiqueta do cooler e retorne somente modelo, número de série e confiança.",
                },
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        }
    ]
    result = (llm or _default_llm()).call(
        messages=messages,
        response_model=EquipmentLabel,
    )
    label = EquipmentLabel.model_validate(result)

    if not label.modelo.strip() or not label.numero_serie.strip():
        return label.model_copy(update={"confianca": 0.0})

    return label
