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


@pytest.mark.parametrize(
    ("assunto", "descricao"),
    [
        ("Cheiro de queimado", ""),
        ("Falha no cooler", "Há faísca ao lado do cabo"),
        ("Cabo danificado", ""),
        ("Falha no cooler", "Foi identificado vazamento"),
    ],
)
def test_initial_critical_risk_routes_urgently_without_asking_for_proximity(
    assunto, descricao
):
    ticket = service.create_case("Bar", assunto, descricao)

    assert ticket["status"] == TicketStatus.SUPPLIER.value
    assert ticket["stage"] == ConversationStage.FINISHED.value
    assert ticket["priority"] == "urgente"
    assert len(ticket["messages"]) == 1
    assert "próximo" not in ticket["messages"][0]["content"].lower()
    assert "foto" not in ticket["messages"][0]["content"].lower()


@pytest.mark.parametrize("equipment_name", ["chopper", "postmix"])
def test_unsupported_equipment_is_rejected_before_cooler_journey(equipment_name):
    ticket = service.create_case("Bar", equipment_name, "Não gela")

    assert ticket["status"] == TicketStatus.SUPPLIER.value
    assert ticket["stage"] == ConversationStage.FINISHED.value
    assert ticket["outcome_reason"] == "equipamento_fora_do_escopo"
    assert "checklist" not in ticket["messages"][0]["content"].lower()
    assert "próximo" not in ticket["messages"][0]["content"].lower()


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


def _ticket_waiting_confirmation(deadline):
    ticket = service.create_case("Bar", "Congela bebidas", "Bebidas congelando")
    db.set_ticket_state(
        ticket["id"],
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        deadline,
    )
    return db.get_ticket(ticket["id"])


@pytest.mark.parametrize("delay", [timedelta(0), timedelta(seconds=1)])
def test_confirmation_at_or_after_deadline_expires_before_positive_parsing(delay):
    deadline = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    ticket = _ticket_waiting_confirmation(deadline)

    updated = service.handle_text(ticket["id"], "sim, resolveu", now=deadline + delay)

    assert updated["status"] == TicketStatus.SUPPLIER.value
    assert updated["stage"] == ConversationStage.FINISHED.value
    assert updated["outcome_reason"] == "sem_confirmacao_pdv"
    assert all(message["content"] != "sim, resolveu" for message in updated["messages"])


def test_confirmation_before_deadline_can_resolve_remotely():
    deadline = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    ticket = _ticket_waiting_confirmation(deadline)

    updated = service.handle_text(
        ticket["id"],
        "SIM!",
        now=deadline - timedelta(microseconds=1),
    )

    assert updated["status"] == TicketStatus.REMOTE_RESOLVED.value


@pytest.mark.parametrize(
    "confirmation",
    ["sim", "SIM!", "Sim, resolveu.", "voltou ao normal"],
)
def test_explicit_confirmation_variants_resolve_remotely(confirmation):
    deadline = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    ticket = _ticket_waiting_confirmation(deadline)

    updated = service.handle_text(
        ticket["id"],
        confirmation,
        now=deadline - timedelta(seconds=1),
    )

    assert updated["status"] == TicketStatus.REMOTE_RESOLVED.value


def test_estou_verificando_remains_pending(monkeypatch):
    deadline = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    ticket = _ticket_waiting_confirmation(deadline)
    monkeypatch.setattr(
        service.client,
        "request_conversation_reply",
        lambda payload: {
            "message": "Tudo bem, aguardo sua confirmação.",
            "risks": [],
            "symptom": "desconhecido",
        },
    )

    updated = service.handle_text(
        ticket["id"],
        "estou verificando",
        now=deadline - timedelta(seconds=1),
    )

    assert updated["status"] == TicketStatus.WAITING_CONFIRMATION.value
    assert updated["stage"] == ConversationStage.CONFIRMATION.value


def test_negative_proximity_keeps_case_available_to_resume():
    ticket = service.create_case("Bar", "Não gela", "")

    updated = service.handle_text(ticket["id"], "não")

    assert updated["stage"] == ConversationStage.PROXIMITY.value
    assert "retomado" in updated["messages"][-1]["content"].lower()
    assert "junto ao cooler" in updated["messages"][-1]["content"].lower()


def test_current_text_rejects_unsupported_equipment_without_agent_call(monkeypatch):
    ticket = service.create_case("Bar", "Falha de refrigeração", "")

    def unexpected_agent_call(payload):
        raise AssertionError("unsupported equipment must not reach the agent")

    monkeypatch.setattr(
        service.client,
        "request_conversation_reply",
        unexpected_agent_call,
    )

    updated = service.handle_text(ticket["id"], "Na verdade é um chopper")

    assert updated["status"] == TicketStatus.SUPPLIER.value
    assert updated["outcome_reason"] == "equipamento_fora_do_escopo"


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
    [("Não liga", "O cooler não liga", "normal")],
)
def test_technical_case_routes_supplier_immediately(assunto, descricao, expected_priority):
    ticket = service.create_case("Bar", assunto, descricao)
    service.handle_text(ticket["id"], "sim")

    updated = service.handle_serial(ticket["id"], "CX-400", "BR-1")

    assert updated["status"] == TicketStatus.SUPPLIER.value
    assert updated["stage"] == ConversationStage.FINISHED.value
    assert updated["priority"] == expected_priority


@pytest.mark.parametrize(
    "operation",
    [
        lambda ticket_id: service.handle_text(ticket_id, "cheiro de queimado"),
        lambda ticket_id: service.handle_label(
            ticket_id,
            {"modelo": "CX-400", "numero_serie": "BR-2", "confianca": 0.99},
            "late.jpg",
        ),
        lambda ticket_id: service.handle_serial(ticket_id, "CX-400", "BR-2"),
    ],
    ids=["late-text", "late-label", "late-serial"],
)
@pytest.mark.parametrize(
    "final_status",
    [TicketStatus.REMOTE_RESOLVED, TicketStatus.SUPPLIER],
)
def test_final_ticket_rejects_mutation(operation, final_status):
    ticket = service.create_case("Bar", "Congela bebidas", "Bebidas congelando")
    db.set_ticket_state(
        ticket["id"],
        final_status,
        ConversationStage.FINISHED,
        reason="final_original",
    )
    before = db.get_ticket(ticket["id"])

    with pytest.raises(ValueError):
        operation(ticket["id"])

    assert db.get_ticket(ticket["id"]) == before


@pytest.mark.parametrize(
    "operation",
    [
        lambda ticket_id: service.handle_label(
            ticket_id,
            {"modelo": "CX-400", "numero_serie": "BR-2", "confianca": 0.99},
            "early.jpg",
        ),
        lambda ticket_id: service.handle_serial(ticket_id, "CX-400", "BR-2"),
    ],
    ids=["label", "serial"],
)
def test_identification_is_rejected_outside_identification_stage(operation):
    ticket = service.create_case("Bar", "Congela bebidas", "Bebidas congelando")
    before = db.get_ticket(ticket["id"])

    with pytest.raises(ValueError):
        operation(ticket["id"])

    assert db.get_ticket(ticket["id"]) == before


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

    assert expired == [ticket["id"]]
    updated = db.get_ticket(ticket["id"])
    assert updated["status"] == TicketStatus.SUPPLIER.value
    assert updated["outcome_reason"] == "sem_confirmacao_pdv"
