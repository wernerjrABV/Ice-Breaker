import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src import db
from src.demo_data import DEMO_CASES, reset_demo_cases, seed_demo_cases
from src.main import app
from src.models import ConversationStage, TicketStatus


EXPECTED_DEMO_CASES = [
    ("DEMO-REMOTE", "Congela bebidas"),
    ("DEMO-DOOR", "Porta não fecha"),
    ("DEMO-SUPPLIER", "Não liga"),
    ("DEMO-URGENT", "Cheiro de queimado"),
]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as test_client:
        yield test_client


def test_seed_creates_four_repeatable_demo_cases(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    first = seed_demo_cases()
    second = seed_demo_cases()

    assert first == second == [ticket_id for ticket_id, _ in EXPECTED_DEMO_CASES]
    assert [(item.ticket_id, item.assunto) for item in DEMO_CASES] == EXPECTED_DEMO_CASES
    assert [db.get_ticket(ticket_id)["assunto"] for ticket_id in first] == [
        subject for _, subject in EXPECTED_DEMO_CASES
    ]
    assert all(len(db.get_ticket(ticket_id)["messages"]) == 1 for ticket_id in first)


def test_seed_repairs_demo_ticket_missing_its_opening(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    case = DEMO_CASES[0]
    db.create_ticket(
        case.ticket_id,
        case.nome_pdv,
        case.assunto,
        case.descricao_base,
    )
    assert db.get_ticket(case.ticket_id)["messages"] == []

    seed_demo_cases()

    repaired = db.get_ticket(case.ticket_id)
    assert len(repaired["messages"]) == 1
    assert repaired["messages"][0]["kind"] == "opening"
    assert "Você está próximo ao equipamento?" in repaired["messages"][0]["content"]


def test_reset_rolls_back_all_demo_changes_when_an_opening_insert_fails(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    seed_demo_cases()
    db.append_message("DEMO-REMOTE", "user", "estado anterior completo")
    before = {
        case.ticket_id: db.get_ticket(case.ticket_id)
        for case in DEMO_CASES
    }
    with db._connect() as conn:
        conn.execute(
            """
            CREATE TRIGGER fail_demo_opening
            BEFORE INSERT ON messages
            WHEN NEW.ticket_id = 'DEMO-SUPPLIER' AND NEW.kind = 'opening'
            BEGIN
                SELECT RAISE(ABORT, 'falha injetada na abertura');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="falha injetada"):
        reset_demo_cases()

    assert {
        case.ticket_id: db.get_ticket(case.ticket_id)
        for case in DEMO_CASES
    } == before


def test_seed_never_commits_tickets_without_all_openings(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    with db._connect() as conn:
        conn.execute(
            """
            CREATE TRIGGER fail_seed_opening
            BEFORE INSERT ON messages
            WHEN NEW.ticket_id = 'DEMO-SUPPLIER' AND NEW.kind = 'opening'
            BEGIN
                SELECT RAISE(ABORT, 'falha injetada no seed');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="falha injetada"):
        seed_demo_cases()

    assert all(db.get_ticket(case.ticket_id) is None for case in DEMO_CASES)


def test_reset_recreates_only_demo_tickets_and_is_idempotent(api):
    seed_demo_cases()
    db.create_ticket("REAL-1", "PDV real", "Não gela", "Preservar este chamado")
    db.append_message("REAL-1", "user", "Mensagem que não pode ser removida")
    unrelated_before = db.get_ticket("REAL-1")

    db.append_message("DEMO-REMOTE", "user", "sim")
    db.set_equipment("DEMO-REMOTE", "CX-400", "ALTERADO", 1.0, None)
    db.set_ticket_state(
        "DEMO-REMOTE",
        TicketStatus.REMOTE_RESOLVED,
        ConversationStage.FINISHED,
        reason="confirmacao_positiva_pdv",
    )

    first = api.post("/demo/reset")
    second = api.post("/demo/reset")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json() == [
        ticket_id for ticket_id, _ in EXPECTED_DEMO_CASES
    ]
    reset_ticket = db.get_ticket("DEMO-REMOTE")
    assert reset_ticket["status"] == TicketStatus.TRIAGE.value
    assert reset_ticket["stage"] == ConversationStage.PROXIMITY.value
    assert reset_ticket["equipment"] is None
    assert len(reset_ticket["messages"]) == 1
    assert db.get_ticket("REAL-1") == unrelated_before


def _create_waiting_ticket(ticket_id: str, deadline: datetime) -> None:
    db.create_ticket(ticket_id, "PDV", "Congela bebidas", "Bebidas congelando")
    db.set_ticket_state(
        ticket_id,
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        deadline,
    )


def test_expiry_rejects_supplied_clock_when_demo_mode_is_disabled(
    api, monkeypatch
):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    deadline = datetime.now(timezone.utc) + timedelta(minutes=30)
    supplied_now = deadline + timedelta(seconds=1)
    _create_waiting_ticket("FUTURE-1", deadline)

    response = api.post(
        "/maintenance/expire-confirmations",
        params={"now": supplied_now.isoformat()},
    )

    assert response.status_code == 403
    assert db.get_ticket("FUTURE-1")["status"] == TicketStatus.WAITING_CONFIRMATION.value


def test_demo_clock_expires_only_exact_demo_ids(api, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "TrUe")
    seed_demo_cases()
    deadline = datetime(2099, 1, 1, tzinfo=timezone.utc)
    supplied_now = deadline + timedelta(seconds=1)
    db.set_ticket_state(
        "DEMO-REMOTE",
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        deadline,
    )
    _create_waiting_ticket("DEMO-REMOTE-COPY", deadline)

    response = api.post(
        "/maintenance/expire-confirmations",
        params={"now": supplied_now.isoformat()},
    )

    assert response.status_code == 200
    assert response.json() == ["DEMO-REMOTE"]
    assert db.get_ticket("DEMO-REMOTE")["outcome_reason"] == "sem_confirmacao_pdv"
    assert (
        db.get_ticket("DEMO-REMOTE-COPY")["status"]
        == TicketStatus.WAITING_CONFIRMATION.value
    )


def test_demo_clock_rejects_malformed_now(api, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    response = api.post(
        "/maintenance/expire-confirmations",
        params={"now": "not-a-datetime"},
    )

    assert response.status_code == 422


def test_expiry_without_supplied_clock_uses_real_clock_for_all_tickets(
    api, monkeypatch
):
    monkeypatch.setenv("DEMO_MODE", "true")
    _create_waiting_ticket(
        "PAST-1",
        datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    response = api.post("/maintenance/expire-confirmations")

    assert response.status_code == 200
    assert response.json() == ["PAST-1"]
    assert db.get_ticket("PAST-1")["status"] == TicketStatus.SUPPLIER.value
