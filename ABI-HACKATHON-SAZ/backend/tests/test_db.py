import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src import db
from src.models import (
    ConversationStage,
    EquipmentType,
    TicketEventCategory,
    TicketEventState,
    TicketEventWrite,
    TicketStatus,
)


def event(category=TicketEventCategory.TICKET_CREATED, title="Chamado recebido"):
    metadata = (
        {"detected": False, "risk_flags": []}
        if category is TicketEventCategory.RISK_EVALUATED
        else {"equipment_type": "cooler"}
    )
    return TicketEventWrite(
        category=category,
        title=title,
        description="Evento público e auditável.",
        state=TicketEventState.COMPLETED,
        metadata=metadata,
    )


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


def test_ticket_events_are_ordered_and_filtered_incrementally(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "events.db")
    db.init_db()
    db.create_ticket("T-EVENT", "PDV", "Não gela", "", events=[event()])
    first = db.list_ticket_events("T-EVENT")[0]
    db.record_ticket_events(
        "T-EVENT",
        [event(TicketEventCategory.RISK_EVALUATED, "Risco verificado")],
    )

    remaining = db.list_ticket_events("T-EVENT", after=int(first["id"]), limit=100)

    assert [item["category"] for item in remaining] == ["risk_evaluated"]
    assert remaining[0]["metadata"] == {"detected": False, "risk_flags": []}
    assert remaining[0]["created_at"].endswith("+00:00")


@pytest.mark.parametrize("metadata_key", ["content", "dialogue", "input"])
def test_ticket_event_metadata_rejects_unknown_content_keys(metadata_key):
    with pytest.raises(ValueError):
        TicketEventWrite(
            category=TicketEventCategory.AGENT_INTERPRETED,
            title="Agente interpretou",
            description="Resposta validada.",
            state=TicketEventState.COMPLETED,
            metadata={metadata_key: "not allowed"},
        )


def test_ticket_event_metadata_rejects_an_approved_key_on_the_wrong_category():
    with pytest.raises(ValueError):
        TicketEventWrite(
            category=TicketEventCategory.TICKET_CREATED,
            title="Chamado recebido",
            description="Evento público e auditável.",
            state=TicketEventState.COMPLETED,
            metadata={"reason": "wrong category"},
        )


@pytest.mark.parametrize(
    ("category", "metadata"),
    [
        (TicketEventCategory.TICKET_CREATED, {"equipment_type": "cooler"}),
        (TicketEventCategory.SCOPE_VALIDATED, {"equipment_type": "cooler"}),
        (TicketEventCategory.RISK_EVALUATED, {"detected": False, "risk_flags": []}),
        (
            TicketEventCategory.STAGE_CHANGED,
            {"from_stage": "aguardando_proximidade", "to_stage": "aguardando_identificacao"},
        ),
        (TicketEventCategory.AGENT_REQUESTED, {"stage": "aguardando_proximidade"}),
        (
            TicketEventCategory.AGENT_INTERPRETED,
            {"reply_key": "solicitar_identificacao", "symptom": "nao_gela", "risk_flags": []},
        ),
        (
            TicketEventCategory.OCR_COMPLETED,
            {"model": "CX-400", "serial": "BR-1", "confidence": 0.79, "manual_required": True},
        ),
        (
            TicketEventCategory.EQUIPMENT_CONFIRMED,
            {"model": "CX-400", "serial": "BR-1", "confidence": 1.0},
        ),
        (
            TicketEventCategory.TRIAGE_DECISION,
            {
                "symptom": "congela_bebidas",
                "outcome": "checklist_remoto",
                "priority": "normal",
                "reason": "checklist_aplicavel",
            },
        ),
        (TicketEventCategory.CHECKLIST_SENT, {"actions": ["Verifique a ventilação."]}),
        (TicketEventCategory.CONFIRMATION_WAITING, {"deadline": "2026-08-25T17:32:09+00:00"}),
        (
            TicketEventCategory.TICKET_RESOLVED,
            {"reason": "confirmacao_positiva_pdv", "saving_brl": 200},
        ),
        (
            TicketEventCategory.SUPPLIER_ROUTED,
            {"reason": "risco_detectado", "priority": "urgente", "saving_brl": 0},
        ),
        (
            TicketEventCategory.CONFIRMATION_EXPIRED,
            {"reason": "sem_confirmacao_pdv", "priority": "normal"},
        ),
    ],
)
def test_ticket_event_metadata_accepts_every_service_shape(category, metadata):
    event = TicketEventWrite(
        category=category,
        title="Agente interpretou",
        description="Resposta validada.",
        state=TicketEventState.COMPLETED,
        metadata=metadata,
    )

    assert event.metadata == metadata


def test_ticket_event_metadata_rejects_nested_or_sensitive_values():
    with pytest.raises(ValueError):
        TicketEventWrite(
            category=TicketEventCategory.AGENT_INTERPRETED,
            title="Agente interpretou",
            description="Resposta validada.",
            state=TicketEventState.COMPLETED,
            metadata={"raw_response": {"secret": "not allowed"}},
        )


def test_state_and_event_roll_back_together(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "atomic.db")
    db.init_db()
    db.create_ticket("T-ATOMIC", "PDV", "Não gela", "")
    invalid = event()
    invalid.title = None  # type: ignore[assignment]

    with pytest.raises(sqlite3.IntegrityError):
        db.set_ticket_state(
            "T-ATOMIC",
            TicketStatus.WAITING_CONFIRMATION,
            ConversationStage.CONFIRMATION,
            events=[invalid],
        )

    assert db.get_ticket("T-ATOMIC")["stage"] == ConversationStage.PROXIMITY.value
