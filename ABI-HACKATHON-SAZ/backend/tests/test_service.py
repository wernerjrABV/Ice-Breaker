from datetime import datetime, timedelta, timezone

import pytest

from src import db, service
from src.models import ConversationStage, TicketStatus


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def test_create_case_uses_exact_backend_owned_opening():
    ticket = service.create_case("Bar do João", "Congela bebidas", "Bebidas congelando")

    assert ticket["stage"] == ConversationStage.PROXIMITY.value
    assert ticket["messages"][0]["content"] == (
        "Olá! Recebi um chamado do Bar do João sobre Congela bebidas. "
        "Quero entender melhor o que está acontecendo e verificar se já consigo ajudar "
        "você agora. Você está próximo ao equipamento?"
    )


def test_remote_resolution_requires_explicit_confirmation():
    ticket = service.create_case("Bar do João", "Congela bebidas", "Bebidas congelando")
    service.handle_text(ticket["id"], "sim")
    service.handle_serial(ticket["id"], "CX-400", "BR-12345")

    waiting = db.get_ticket(ticket["id"])
    assert waiting["status"] == TicketStatus.WAITING_CONFIRMATION.value
    assert datetime.fromisoformat(waiting["confirmation_deadline"]).tzinfo is not None

    service.handle_text(ticket["id"], "sim, resolveu")
    resolved = db.get_ticket(ticket["id"])
    assert resolved["status"] == TicketStatus.REMOTE_RESOLVED.value


def test_negative_confirmation_routes_supplier():
    ticket = service.create_case("Bar", "Não gela", "")
    service.handle_text(ticket["id"], "sim")
    service.handle_serial(ticket["id"], "CX-400", "BR-1")
    service.handle_text(ticket["id"], "não resolveu")

    assert db.get_ticket(ticket["id"])["status"] == TicketStatus.SUPPLIER.value


def test_negative_proximity_keeps_case_available_to_resume():
    ticket = service.create_case("Bar", "Não gela", "")

    updated = service.handle_text(ticket["id"], "não")

    assert updated["stage"] == ConversationStage.PROXIMITY.value
    assert "retomado" in updated["messages"][-1]["content"].lower()
    assert "junto ao cooler" in updated["messages"][-1]["content"].lower()


@pytest.mark.parametrize(
    ("numero_serie", "confianca"),
    [("BR-12345", 0.79), ("", 0.98)],
)
def test_uncertain_or_empty_ocr_requires_manual_serial(numero_serie, confianca):
    ticket = service.create_case("Bar", "Congela bebidas", "Bebidas congelando")
    service.handle_text(ticket["id"], "sim")

    updated = service.handle_label(
        ticket["id"],
        {"modelo": "CX-400", "numero_serie": numero_serie, "confianca": confianca},
        "etiqueta.jpg",
    )

    assert updated["status"] == TicketStatus.TRIAGE.value
    assert updated["stage"] == ConversationStage.IDENTIFICATION.value
    assert updated["equipment"] == {
        "modelo": "CX-400",
        "numero_serie": numero_serie,
        "confianca": confianca,
        "image_name": "etiqueta.jpg",
    }
    assert "serial manualmente" in updated["messages"][-1]["content"].lower()


@pytest.mark.parametrize(
    ("assunto", "descricao", "expected_priority"),
    [
        ("Não liga", "O cooler não liga", "normal"),
        ("Cheiro de queimado", "Há cheiro de queimado", "urgente"),
    ],
)
def test_technical_or_risk_case_routes_supplier_immediately(
    assunto, descricao, expected_priority
):
    ticket = service.create_case("Bar", assunto, descricao)
    service.handle_text(ticket["id"], "sim")

    updated = service.handle_serial(ticket["id"], "CX-400", "BR-1")

    assert updated["status"] == TicketStatus.SUPPLIER.value
    assert updated["stage"] == ConversationStage.FINISHED.value
    assert updated["priority"] == expected_priority


def test_expired_confirmation_routes_supplier_with_timeout_reason():
    ticket = service.create_case("Bar", "Congela bebidas", "Bebidas congelando")
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.set_ticket_state(
        ticket["id"],
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        expired_at,
    )

    expired = service.expire_confirmations()

    assert [item["id"] for item in expired] == [ticket["id"]]
    assert expired[0]["status"] == TicketStatus.SUPPLIER.value
    assert expired[0]["outcome_reason"] == "sem_confirmacao_pdv"
