import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

AGENT_API_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8000/kickoff")
AGENT_SERVICE_URL = os.getenv(
    "AGENT_SERVICE_URL", AGENT_API_URL.removesuffix("/kickoff").rstrip("/")
)


def call_agent_kickoff(inputs: dict[str, Any]) -> Any:
    response = requests.post(AGENT_API_URL, json=inputs, timeout=300)
    response.raise_for_status()
    return response.json()


def read_equipment_label(image_data_url: str) -> dict[str, Any]:
    response = requests.post(
        f"{AGENT_SERVICE_URL}/label/read",
        json={"image_data_url": image_data_url},
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def request_conversation_reply(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{AGENT_SERVICE_URL}/conversation/respond",
        json=payload,
        timeout=300,
    )
    response.raise_for_status()
    return response.json()
