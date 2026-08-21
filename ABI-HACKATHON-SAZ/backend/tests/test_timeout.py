from datetime import datetime, timedelta, timezone

from src import db, service
from src.models import ConversationStage, SupplierSummary, TicketStatus


def test_timeout_routes_and_builds_supplier_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    ticket = service.create_case("Mercado Central", "Não gela", "Baixa refrigeração")
    service.handle_text(ticket["id"], "sim")
    service.handle_serial(ticket["id"], "CX-400", "BR-9")
    service.handle_text(ticket["id"], "sim, os dados estão corretos")
    deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.set_ticket_state(
        ticket["id"],
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        deadline,
    )

    assert service.expire_confirmations() == [ticket["id"]]

    summary = service.supplier_summary(ticket["id"])
    assert isinstance(summary, SupplierSummary)
    assert summary.motivo == "sem_confirmacao_pdv"
    assert summary.equipamento is not None
    assert summary.equipamento.numero_serie == "BR-9"
    assert summary.acoes_tentadas == [
        "Confira se a ventilação externa está livre.",
        "Verifique se a porta fecha completamente.",
        "Verifique o ajuste de temperatura.",
        "Observe se há gelo visível bloqueando a circulação.",
    ]


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
    service.handle_text(ticket["id"], "sim, os dados estão corretos")
    service.handle_text(ticket["id"], "não resolveu")

    summary = service.supplier_summary(ticket["id"])

    assert summary.acoes_tentadas == [
        "Confira se a ventilação externa está livre.",
        "Verifique se a porta fecha completamente.",
        "Verifique o ajuste de temperatura.",
        "Observe se há gelo visível bloqueando a circulação.",
    ]


def test_urgent_supplier_summary_supports_pre_identification_equipment(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    ticket = service.create_case(
        "Conveniência Estação",
        "Cheiro a queimado",
        "Odor forte vindo do equipamento",
    )

    summary = service.supplier_summary(ticket["id"])
    assert summary.equipamento is None
    assert summary.prioridade.value == "urgente"
    assert summary.motivo == "Risco crítico identificado."
    assert [evidence.tipo for evidence in summary.evidencias] == [
        "descricao_inicial"
    ]
    assert summary.evidencias[0].descricao == "Odor forte vindo do equipamento"


def test_timeout_summary_keeps_manual_correction_photo_and_relevant_evidence(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    ticket = service.create_case("Mercado", "Não gela", "Temperatura alta")
    service.handle_text(ticket["id"], "sim")
    service.handle_label(
        ticket["id"],
        {"modelo": "CX-400", "numero_serie": "", "confianca": 0.20},
        "foto-etiqueta.jpg",
    )
    service.handle_serial(ticket["id"], "CX-400", "BR-MANUAL")
    service.handle_text(ticket["id"], "sim, os dados estão corretos")
    deadline = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.set_ticket_state(
        ticket["id"],
        TicketStatus.WAITING_CONFIRMATION,
        ConversationStage.CONFIRMATION,
        deadline,
    )

    assert service.expire_confirmations() == [ticket["id"]]
    summary = service.supplier_summary(ticket["id"])

    assert summary.equipamento is not None
    assert summary.equipamento.foto_etiqueta == "foto-etiqueta.jpg"
    assert summary.equipamento.numero_serie == "BR-MANUAL"
    assert any(
        evidence.tipo == "foto_etiqueta"
        and evidence.descricao == "foto-etiqueta.jpg"
        for evidence in summary.evidencias
    )
