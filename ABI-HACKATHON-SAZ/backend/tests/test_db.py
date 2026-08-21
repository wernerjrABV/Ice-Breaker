import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src import db
from src.models import ConversationStage, TicketStatus


def test_ticket_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.create_ticket("T-1", "Bar do João", "Congela bebidas", "Bebidas congelando")
    db.append_message("T-1", "assistant", "Você está próximo ao equipamento?")
    db.set_equipment("T-1", "CX-400", "BR-12345", 0.98, "label.jpg")
    ticket = db.get_ticket("T-1")
    assert ticket["nome_pdv"] == "Bar do João"
    assert ticket["equipment"]["numero_serie"] == "BR-12345"
    assert ticket["messages"][0]["role"] == "assistant"


def test_lists_only_expired_waiting_confirmations(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.create_ticket("T-2", "Mercado", "Não gela", "")
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.set_ticket_state("T-2", TicketStatus.WAITING_CONFIRMATION, ConversationStage.CONFIRMATION, expired)
    assert [item["id"] for item in db.list_expired_confirmations()] == ["T-2"]


def test_rejects_orphan_messages_and_equipment(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    with pytest.raises(sqlite3.IntegrityError):
        db.append_message("missing", "assistant", "orphan")
    with pytest.raises(sqlite3.IntegrityError):
        db.set_equipment("missing", "CX-400", "BR-12345", 0.98, None)
