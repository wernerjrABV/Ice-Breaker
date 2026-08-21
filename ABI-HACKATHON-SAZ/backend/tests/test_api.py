from fastapi.testclient import TestClient
import pytest

from src import client as agent_client
from src import db
from src.main import app
from src.models import ConversationStage, TicketStatus


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as test_client:
        yield test_client


def test_ticket_api_journey_and_missing_ticket(api):
    created_response = api.post(
        "/tickets",
        json={
            "nome_pdv": "Bar do João",
            "assunto": "Congela bebidas",
            "descricao_base": "Bebidas congelando",
        },
    )
    assert created_response.status_code == 201
    ticket_id = created_response.json()["id"]

    fetched = api.get(f"/tickets/{ticket_id}")
    assert fetched.status_code == 200
    assert fetched.json()["nome_pdv"] == "Bar do João"

    answered = api.post(f"/tickets/{ticket_id}/messages", json={"content": "sim"})
    assert answered.status_code == 200
    assert answered.json()["stage"] == ConversationStage.IDENTIFICATION.value

    assert api.get("/tickets/missing").status_code == 404


def test_serial_and_expiration_routes(api):
    ticket = api.post(
        "/tickets",
        json={
            "nome_pdv": "Bar",
            "assunto": "Não gela",
            "descricao_base": "Baixa refrigeração",
        },
    ).json()
    api.post(f"/tickets/{ticket['id']}/messages", json={"content": "sim"})

    identified = api.post(
        f"/tickets/{ticket['id']}/equipment/serial",
        json={"modelo": "CX-400", "numero_serie": "BR-1"},
    )
    assert identified.status_code == 200
    assert identified.json()["status"] == TicketStatus.WAITING_CONFIRMATION.value

    expired = api.post("/maintenance/expire-confirmations")
    assert expired.status_code == 200
    assert expired.json() == []


@pytest.mark.parametrize(
    "label",
    [
        {"modelo": "CX-400", "numero_serie": "BR-1", "confianca": 0.79},
        {"modelo": "CX-400", "numero_serie": "", "confianca": 0.98},
    ],
)
def test_photo_api_requires_user_facing_manual_serial_fallback(api, monkeypatch, label):
    ticket = api.post(
        "/tickets",
        json={
            "nome_pdv": "Bar",
            "assunto": "Congela bebidas",
            "descricao_base": "Bebidas congelando",
        },
    ).json()
    api.post(f"/tickets/{ticket['id']}/messages", json={"content": "sim"})

    captured = {}

    def fake_read_equipment_label(image_data_url):
        captured["image_data_url"] = image_data_url
        return label

    monkeypatch.setattr(agent_client, "read_equipment_label", fake_read_equipment_label)

    response = api.post(
        f"/tickets/{ticket['id']}/equipment/photo",
        files={"photo": ("etiqueta.jpg", b"image-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert captured["image_data_url"].startswith("data:image/jpeg;base64,")
    assert body["stage"] == ConversationStage.IDENTIFICATION.value
    assert "serial manualmente" in body["messages"][-1]["content"].lower()


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.raise_called = False

    def raise_for_status(self):
        self.raise_called = True

    def json(self):
        assert self.raise_called
        return self.payload


@pytest.mark.parametrize(
    ("function_name", "endpoint", "payload", "expected"),
    [
        (
            "read_equipment_label",
            "/label/read",
            {"image_data_url": "data:image/jpeg;base64,AA=="},
            {"modelo": "CX-400", "numero_serie": "BR-1", "confianca": 0.98},
        ),
        (
            "request_conversation_reply",
            "/conversation/respond",
            {"stage": "aguardando_proximidade"},
            {"message": "Você está perto?", "risks": [], "symptom": "desconhecido"},
        ),
    ],
)
def test_agent_clients_post_to_expected_endpoint(
    monkeypatch, function_name, endpoint, payload, expected
):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(expected)

    monkeypatch.setattr(agent_client.requests, "post", fake_post)

    function = getattr(agent_client, function_name)
    argument = payload["image_data_url"] if function_name == "read_equipment_label" else payload
    assert function(argument) == expected
    assert calls == [
        (
            f"http://127.0.0.1:8000{endpoint}",
            {"json": payload, "timeout": 300},
        )
    ]
