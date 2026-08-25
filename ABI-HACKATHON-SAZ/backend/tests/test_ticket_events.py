from datetime import datetime, timedelta, timezone

import pytest

from src import db, service


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "events.db")
    db.init_db()


def categories(ticket_id: str) -> list[str]:
    return [str(item["category"]) for item in db.list_ticket_events(ticket_id)]


def test_remote_resolution_records_auditable_decisions(monkeypatch):
    monkeypatch.setattr(
        service.client,
        "request_conversation_reply",
        lambda payload: {"reply_key": "solicitar_identificacao", "risks": [], "symptom": "desconhecido"},
    )
    ticket = service.create_case("PDV", "Congela bebidas", "Bebidas congelando")
    ticket_id = str(ticket["id"])
    service.handle_text(ticket_id, "sim")
    service.handle_serial(ticket_id, "CX-400", "BR-1")
    service.handle_text(ticket_id, "sim, os dados estão corretos")
    service.handle_text(ticket_id, "sim, resolveu")

    history = db.list_ticket_events(ticket_id)
    assert "ticket_created" in categories(ticket_id)
    assert "risk_evaluated" in categories(ticket_id)
    assert "equipment_confirmed" in categories(ticket_id)
    assert "triage_decision" in categories(ticket_id)
    assert "checklist_sent" in categories(ticket_id)
    assert "confirmation_waiting" in categories(ticket_id)
    assert history[-1]["category"] == "ticket_resolved"
    assert history[-1]["metadata"]["saving_brl"] == 200
    assert all("message" not in item["metadata"] for item in history)


def test_critical_risk_records_warning_without_agent_request():
    ticket = service.create_case("PDV", "Cheiro de queimado", "Odor no cooler")
    history = db.list_ticket_events(str(ticket["id"]))

    assert [item["category"] for item in history][-3:] == [
        "risk_evaluated",
        "stage_changed",
        "supplier_routed",
    ]
    assert history[-2]["metadata"] == {
        "from_stage": "aguardando_proximidade",
        "to_stage": "finalizado",
    }
    assert history[-1]["state"] == "warning"
    assert history[-1]["metadata"]["priority"] == "urgente"
    assert "agent_requested" not in categories(str(ticket["id"]))


@pytest.mark.parametrize(
    ("confidence", "manual_required"),
    [(0.98, False), (0.79, True)],
)
def test_ocr_event_exposes_only_safe_label_fields(confidence, manual_required):
    ticket = service.create_case("PDV", "Não gela", "Cooler não refrigera")
    ticket_id = str(ticket["id"])
    service.handle_text(ticket_id, "sim")
    service.handle_label(
        ticket_id,
        {"modelo": "CX-400", "numero_serie": "BR-1", "confianca": confidence},
        "etiqueta.jpg",
    )

    ocr = next(item for item in db.list_ticket_events(ticket_id) if item["category"] == "ocr_completed")
    assert ocr["metadata"] == {
        "confidence": confidence,
        "manual_required": manual_required,
        "model": "CX-400",
        "serial": "BR-1",
    }


def test_confirmation_expiry_records_zero_saving():
    ticket = service.create_case("PDV", "Congela bebidas", "Bebidas congelando")
    ticket_id = str(ticket["id"])
    service.handle_text(ticket_id, "sim")
    service.handle_serial(ticket_id, "CX-400", "BR-1")
    waiting = service.handle_text(ticket_id, "sim, os dados estão corretos")
    deadline = datetime.fromisoformat(str(waiting["confirmation_deadline"]))

    service.expire_confirmations(deadline + timedelta(seconds=1))

    history = db.list_ticket_events(ticket_id)
    assert history[-2]["category"] == "confirmation_expired"
    assert history[-1]["category"] == "supplier_routed"
    assert history[-1]["metadata"]["saving_brl"] == 0
