import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src import db
from src.models import ConversationStage, EquipmentType, TicketStatus


def test_ticket_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.create_ticket(
        "T-1",
        "Bar do João",
        "Congela bebidas",
        "Bebidas congelando",
        EquipmentType.GELADEIRA,
    )
    db.append_message("T-1", "assistant", "Você está próximo ao equipamento?")
    db.set_equipment("T-1", "CX-400", "BR-12345", 0.98, "label.jpg")
    ticket = db.get_ticket("T-1")
    assert ticket["nome_pdv"] == "Bar do João"
    assert ticket["equipment_type"] == "geladeira"
    assert ticket["equipment"]["numero_serie"] == "BR-12345"
    assert ticket["messages"][0]["role"] == "assistant"


def test_ticket_round_trip_preserves_individual_safe_checklist_actions(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.create_ticket("T-ACTIONS", "PDV", "Não gela", "Baixa refrigeração")

    db.record_checklist_actions(
        "T-ACTIONS",
        [
            "Confira se a ventilação externa está livre.",
            "Verifique se a porta fecha completamente.",
        ],
    )

    assert db.get_ticket("T-ACTIONS")["checklist_actions"] == [
        "Confira se a ventilação externa está livre.",
        "Verifique se a porta fecha completamente.",
    ]


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


def test_init_db_migrates_legacy_tickets_without_losing_data(tmp_path, monkeypatch):
    database = tmp_path / "legacy.db"
    monkeypatch.setattr(db, "DB_PATH", database)
    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            CREATE TABLE tickets (
                id TEXT PRIMARY KEY,
                nome_pdv TEXT NOT NULL,
                assunto TEXT NOT NULL,
                descricao_base TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                confirmation_deadline TEXT,
                priority TEXT NOT NULL,
                outcome_reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO tickets VALUES (
                'LEGACY-1', 'PDV legado', 'Não gela', 'Registro preservado',
                'em_triagem', 'aguardando_proximidade', NULL, 'normal', '',
                '2026-08-21T00:00:00+00:00', '2026-08-21T00:00:00+00:00'
            )
            """
        )

    db.init_db()

    migrated = db.get_ticket("LEGACY-1")
    assert migrated["nome_pdv"] == "PDV legado"
    assert migrated["descricao_base"] == "Registro preservado"
    assert migrated["equipment_type"] == "cooler"


def test_bare_string_expiry_filter_is_one_exact_ticket_id(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.create_ticket("T-STRING", "PDV", "Não gela", "")
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.set_ticket_state(
        "T-STRING",
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        expired,
    )

    assert [
        item["id"]
        for item in db.list_expired_confirmations(ticket_ids="T-STRING")
    ] == ["T-STRING"]
