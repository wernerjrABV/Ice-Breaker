from datetime import datetime, timedelta, timezone

from src import db, service
from src.models import ConversationStage, TicketStatus


def test_timeout_routes_and_builds_supplier_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    ticket = service.create_case("Mercado Central", "Não gela", "Baixa refrigeração")
    db.set_equipment(ticket["id"], "CX-400", "BR-9", 1.0, None)
    db.append_message(ticket["id"], "assistant", "Verifique se a porta fecha.", "checklist")
    deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.set_ticket_state(
        ticket["id"],
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        deadline,
    )

    assert service.expire_confirmations() == [ticket["id"]]

    summary = service.supplier_summary(ticket["id"])
    assert summary["motivo"] == "sem_confirmacao_pdv"
    assert summary["numero_serie"] == "BR-9"
    assert summary["acoes_tentadas"] == ["Verifique se a porta fecha."]


def test_expire_confirmations_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    ticket = service.create_case("Mercado Central", "Não gela", "Baixa refrigeração")
    deadline = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    db.set_ticket_state(
        ticket["id"],
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        deadline,
    )

    assert service.expire_confirmations(now=deadline) == [ticket["id"]]
    assert service.expire_confirmations(now=deadline) == []


def test_supplier_summary_includes_only_safe_checklist_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    ticket = service.create_case("Mercado Central", "Não gela", "Baixa refrigeração")
    service.handle_text(ticket["id"], "sim")
    service.handle_serial(ticket["id"], "CX-400", "BR-9")
    service.handle_text(ticket["id"], "não resolveu")

    summary = service.supplier_summary(ticket["id"])

    assert summary["acoes_tentadas"] == [
        "Siga estas verificações seguras: 1. Verifique o ajuste de temperatura. "
        "2. Confira se há obstrução ou se a organização interna está adequada. "
        "3. Confira se a ventilação externa está livre. "
        "O cooler voltou a funcionar corretamente?"
    ]
