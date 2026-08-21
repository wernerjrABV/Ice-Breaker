import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

AGENT_API_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8000/kickoff")


def call_agent_kickoff(inputs: dict[str, Any]) -> Any:
    response = requests.post(AGENT_API_URL, json=inputs, timeout=300)
    response.raise_for_status()
    return response.json()
