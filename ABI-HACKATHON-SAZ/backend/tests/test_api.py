from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest
import requests

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
            "equipment_type": "cooler",
        },
    )
    assert created_response.status_code == 201
    ticket_id = created_response.json()["id"]

    fetched = api.get(f"/tickets/{ticket_id}")
    assert fetched.status_code == 200
    assert fetched.json()["nome_pdv"] == "Bar do João"
    assert fetched.json()["equipment_type"] == "cooler"

    answered = api.post(f"/tickets/{ticket_id}/messages", json={"content": "sim"})
    assert answered.status_code == 200
    assert answered.json()["stage"] == ConversationStage.IDENTIFICATION.value

    assert api.get("/tickets/missing").status_code == 404


def test_demo_ticket_api_accepts_only_subject_and_uses_fixed_pdv(api):
    response = api.post("/demo/tickets", json={"assunto": "Cooler não gela"})

    assert response.status_code == 201
    assert response.json()["nome_pdv"] == "PDV Demonstração"


def test_demo_ticket_api_rejects_blank_subject(api):
    assert api.post("/demo/tickets", json={"assunto": "  "}).status_code == 422


def test_demo_ticket_api_rejects_fields_beyond_subject(api):
    response = api.post(
        "/demo/tickets",
        json={"assunto": "Cooler não gela", "nome_pdv": "Outro PDV"},
    )

    assert response.status_code == 422


def test_demo_ticket_api_strips_subject_before_creating_ticket(api):
    response = api.post(
        "/demo/tickets",
        json={"assunto": "  Cooler não gela  "},
    )

    assert response.status_code == 201
    assert response.json()["assunto"] == "Cooler não gela"


@pytest.mark.parametrize(
    ("assunto", "expected_status"),
    [("a" * 500, 201), ("a" * 501, 422)],
)
def test_demo_ticket_api_enforces_subject_length(api, assunto, expected_status):
    response = api.post("/demo/tickets", json={"assunto": assunto})

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("equipment_type", "assunto"),
    [
        ("ar-condicionado", "Não gela"),
        ("cooler", "O post-mix não gela"),
        ("cooler", "A geladeira não gela"),
    ],
)
def test_ticket_api_rejects_unsupported_or_contradictory_equipment(
    api, equipment_type, assunto
):
    response = api.post(
        "/tickets",
        json={
            "nome_pdv": "Bar",
            "assunto": assunto,
            "descricao_base": "",
            "equipment_type": equipment_type,
        },
    )

    assert response.status_code == 422
    assert any(
        phrase in response.text.lower()
        for phrase in ("cooler ou geladeira", "contradiz")
    )


def test_ticket_api_routes_risk_before_narrative_scope_contradiction(api):
    response = api.post(
        "/tickets",
        json={
            "nome_pdv": "Bar",
            "assunto": "Chopper com faísca",
            "descricao_base": "Risco imediato",
            "equipment_type": "cooler",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == TicketStatus.SUPPLIER.value
    assert response.json()["priority"] == "urgente"


def test_urgent_supplier_response_and_get_expose_nullable_typed_summary(api):
    created = api.post(
        "/tickets",
        json={
            "nome_pdv": "Conveniência Estação",
            "assunto": "Cheiro a queimado",
            "descricao_base": "Odor forte vindo do cooler",
            "equipment_type": "cooler",
        },
    )

    assert created.status_code == 201
    summary = created.json()["supplier_summary"]
    assert summary["nome_pdv"] == "Conveniência Estação"
    assert summary["assunto"] == "Cheiro a queimado"
    assert summary["equipamento"] is None
    assert summary["prioridade"] == "urgente"
    assert summary["motivo"] == "Risco crítico identificado."
    assert summary["evidencias"] == [
        {
            "tipo": "descricao_inicial",
            "descricao": "Odor forte vindo do cooler",
        }
    ]
    assert summary["acoes_tentadas"] == []

    fetched = api.get(f"/tickets/{created.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["supplier_summary"] == summary


def test_post_checklist_supplier_response_exposes_actual_actions(api):
    created = api.post(
        "/tickets",
        json={
            "nome_pdv": "Mercado Central",
            "assunto": "Não gela",
            "descricao_base": "Temperatura alta",
            "equipment_type": "cooler",
        },
    ).json()
    ticket_id = created["id"]
    api.post(f"/tickets/{ticket_id}/messages", json={"content": "sim"})
    api.post(
        f"/tickets/{ticket_id}/equipment/serial",
        json={"modelo": "CX-400", "numero_serie": "BR-1"},
    )
    api.post(
        f"/tickets/{ticket_id}/messages",
        json={"content": "sim, os dados estão corretos"},
    )

    routed = api.post(
        f"/tickets/{ticket_id}/messages",
        json={"content": "não resolveu"},
    )

    assert routed.status_code == 200
    summary = routed.json()["supplier_summary"]
    assert summary["equipamento"]["numero_serie"] == "BR-1"
    assert summary["acoes_tentadas"] == [
        "Confira se a ventilação externa está livre.",
        "Verifique se a porta fecha completamente.",
        "Verifique o ajuste de temperatura.",
        "Observe se há gelo visível bloqueando a circulação.",
    ]
    assert api.get(f"/tickets/{ticket_id}").json()["supplier_summary"] == summary


def test_timeout_after_manual_photo_correction_exposes_photo_in_rest_summary(
    api, monkeypatch
):
    created = api.post(
        "/tickets",
        json={
            "nome_pdv": "Mercado",
            "assunto": "Não gela",
            "descricao_base": "Temperatura alta",
            "equipment_type": "cooler",
        },
    ).json()
    ticket_id = created["id"]
    api.post(f"/tickets/{ticket_id}/messages", json={"content": "sim"})
    monkeypatch.setattr(
        agent_client,
        "read_equipment_label",
        lambda image_data_url: {
            "modelo": "CX-400",
            "numero_serie": "",
            "confianca": 0.20,
        },
    )
    api.post(
        f"/tickets/{ticket_id}/equipment/photo",
        files={"photo": ("foto-etiqueta.jpg", b"image", "image/jpeg")},
    )
    api.post(
        f"/tickets/{ticket_id}/equipment/serial",
        json={"modelo": "CX-400", "numero_serie": "BR-MANUAL"},
    )
    api.post(
        f"/tickets/{ticket_id}/messages",
        json={"content": "sim, os dados estão corretos"},
    )
    db.set_ticket_state(
        ticket_id,
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    expired = api.post("/maintenance/expire-confirmations")
    fetched = api.get(f"/tickets/{ticket_id}")

    assert expired.status_code == 200
    assert expired.json() == [ticket_id]
    summary = fetched.json()["supplier_summary"]
    assert summary["equipamento"]["foto_etiqueta"] == "foto-etiqueta.jpg"
    assert summary["equipamento"]["numero_serie"] == "BR-MANUAL"
    assert {item["tipo"] for item in summary["evidencias"]} >= {
        "descricao_inicial",
        "foto_etiqueta",
    }


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
    assert (
        identified.json()["stage"]
        == ConversationStage.EQUIPMENT_CONFIRMATION.value
    )
    diagnosed = api.post(
        f"/tickets/{ticket['id']}/messages",
        json={"content": "sim, os dados estão corretos"},
    )
    assert diagnosed.status_code == 200
    assert diagnosed.json()["status"] == TicketStatus.WAITING_CONFIRMATION.value

    db.set_ticket_state(
        ticket["id"],
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    expired = api.post("/maintenance/expire-confirmations")
    assert expired.status_code == 200
    assert expired.json() == [ticket["id"]]


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


def test_confident_photo_api_waits_for_explicit_equipment_confirmation(
    api, monkeypatch
):
    ticket = api.post(
        "/tickets",
        json={
            "nome_pdv": "Bar",
            "assunto": "Não gela",
            "descricao_base": "Baixa refrigeração",
            "equipment_type": "cooler",
        },
    ).json()
    api.post(f"/tickets/{ticket['id']}/messages", json={"content": "sim"})
    monkeypatch.setattr(
        agent_client,
        "read_equipment_label",
        lambda image_data_url: {
            "modelo": "CX-400",
            "numero_serie": "BR-1",
            "confianca": 0.98,
        },
    )

    identified = api.post(
        f"/tickets/{ticket['id']}/equipment/photo",
        files={"photo": ("etiqueta.jpg", b"image-bytes", "image/jpeg")},
    )

    assert identified.status_code == 200
    assert (
        identified.json()["stage"]
        == ConversationStage.EQUIPMENT_CONFIRMATION.value
    )
    assert identified.json()["equipment"]["image_name"] == "etiqueta.jpg"
    assert not any(
        message["kind"] == "checklist"
        for message in identified.json()["messages"]
    )


def test_photo_api_rejects_final_ticket_before_ocr(api, monkeypatch):
    ticket = api.post(
        "/tickets",
        json={
            "nome_pdv": "Bar",
            "assunto": "Congela bebidas",
            "descricao_base": "Bebidas congelando",
        },
    ).json()
    db.set_ticket_state(
        ticket["id"],
        TicketStatus.REMOTE_RESOLVED,
        ConversationStage.FINISHED,
        reason="confirmacao_positiva_pdv",
    )

    def unexpected_ocr_call(image_data_url):
        raise AssertionError("final tickets must be rejected before OCR")

    monkeypatch.setattr(agent_client, "read_equipment_label", unexpected_ocr_call)

    response = api.post(
        f"/tickets/{ticket['id']}/equipment/photo",
        files={"photo": ("late.jpg", b"late-image", "image/jpeg")},
    )

    assert response.status_code == 409
    assert db.get_ticket(ticket["id"])["equipment"] is None


def test_photo_agent_failure_is_reported_in_portuguese(api, monkeypatch):
    ticket = api.post(
        "/tickets",
        json={
            "nome_pdv": "Bar",
            "assunto": "Não gela",
            "descricao_base": "Baixa refrigeração",
        },
    ).json()
    api.post(f"/tickets/{ticket['id']}/messages", json={"content": "sim"})

    def fail_label_read(image_data_url):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(agent_client, "read_equipment_label", fail_label_read)

    response = api.post(
        f"/tickets/{ticket['id']}/equipment/photo",
        files={"photo": ("etiqueta.jpg", b"image-bytes", "image/jpeg")},
    )

    assert response.status_code == 502
    assert "Falha ao consultar a API do agente" in response.json()["detail"]
    assert "Agent API call failed" not in response.text


def test_kickoff_errors_and_missing_async_requests_are_localized(api, monkeypatch):
    def fail_kickoff(inputs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("src.main.call_agent_kickoff", fail_kickoff)

    failed = api.post("/kickoff", json={"subject": "Não gela"})
    missing = api.get("/kickoff/async/nao-existe")

    assert failed.status_code == 502
    assert "Falha ao consultar a API do agente" in failed.json()["detail"]
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Solicitação não encontrada."


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
            {
                "reply_key": "confirmar_proximidade",
                "risks": [],
                "symptom": "desconhecido",
            },
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


def test_ticket_events_endpoint_is_incremental_and_terminal(api):
    created = api.post(
        "/tickets",
        json={
            "nome_pdv": "Bar do João",
            "assunto": "Cheiro de queimado",
            "descricao_base": "Odor no cooler",
            "equipment_type": "cooler",
        },
    ).json()

    first = api.get(f"/tickets/{created['id']}/events", params={"limit": 1})
    assert first.status_code == 200
    assert len(first.json()["items"]) == 1
    assert first.json()["terminal"] is True

    after = first.json()["last_id"]
    second = api.get(
        f"/tickets/{created['id']}/events",
        params={"after": after, "limit": 100},
    )
    assert second.status_code == 200
    assert all(item["id"] > after for item in second.json()["items"])
    assert second.json()["last_id"] >= after


@pytest.mark.parametrize("query", ["after=-1", "limit=0", "limit=201"])
def test_ticket_events_endpoint_validates_bounds(api, query):
    assert api.get(f"/tickets/T-1/events?{query}").status_code == 422


def test_ticket_events_endpoint_returns_404_for_missing_ticket(api):
    assert api.get("/tickets/missing/events").status_code == 404
