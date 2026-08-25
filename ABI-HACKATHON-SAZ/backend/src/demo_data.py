import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from src import db
from src.models import (
    ConversationStage,
    EquipmentType,
    TicketEventCategory,
    TicketEventWrite,
    TicketStatus,
)


@dataclass(frozen=True)
class DemoCase:
    ticket_id: str
    nome_pdv: str
    assunto: str
    descricao_base: str
    equipment_type: EquipmentType


DEMO_CASES = (
    DemoCase(
        "DEMO-REMOTE",
        "Mercado Central",
        "Congela bebidas",
        "As bebidas estão congelando dentro do cooler.",
        EquipmentType.COOLER,
    ),
    DemoCase(
        "DEMO-DOOR",
        "Bar do João",
        "Porta não fecha",
        "A porta do cooler não permanece fechada.",
        EquipmentType.COOLER,
    ),
    DemoCase(
        "DEMO-SUPPLIER",
        "Padaria Primavera",
        "Não liga",
        "O cooler não liga.",
        EquipmentType.COOLER,
    ),
    DemoCase(
        "DEMO-URGENT",
        "Conveniência Estação",
        "Cheiro de queimado",
        "O PDV precisa relatar o sinal de risco durante a triagem.",
        EquipmentType.COOLER,
    ),
)
DEMO_TICKET_IDS = tuple(case.ticket_id for case in DEMO_CASES)


def _opening(case: DemoCase) -> str:
    return (
        f"Olá! Recebi um chamado do {case.nome_pdv} sobre {case.assunto}. "
        "Quero entender melhor o que está acontecendo e verificar se já consigo ajudar "
        "você agora. Você está próximo ao equipamento?"
    )


def _initial_events(case: DemoCase) -> list[TicketEventWrite]:
    return [
        TicketEventWrite(
            category=TicketEventCategory.TICKET_CREATED,
            title="Chamado recebido",
            description="O CoolCare iniciou a triagem.",
            state="completed",
            metadata={"equipment_type": case.equipment_type.value},
        ),
        TicketEventWrite(
            category=TicketEventCategory.SCOPE_VALIDATED,
            title="Escopo validado",
            description="O equipamento está no escopo do CoolCare.",
            state="completed",
            metadata={"equipment_type": case.equipment_type.value},
        ),
        TicketEventWrite(
            category=TicketEventCategory.RISK_EVALUATED,
            title="Risco verificado",
            description="A descrição inicial foi avaliada por regras de segurança.",
            state="completed",
            metadata={"detected": False, "risk_flags": []},
        ),
    ]


def _delete_case(conn: sqlite3.Connection, ticket_id: str) -> None:
    conn.execute("DELETE FROM ticket_events WHERE ticket_id = ?", (ticket_id,))
    conn.execute("DELETE FROM checklist_actions WHERE ticket_id = ?", (ticket_id,))
    conn.execute("DELETE FROM equipment WHERE ticket_id = ?", (ticket_id,))
    conn.execute("DELETE FROM messages WHERE ticket_id = ?", (ticket_id,))
    conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))


def _insert_case(conn: sqlite3.Connection, case: DemoCase) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO tickets (
            id, nome_pdv, assunto, descricao_base, equipment_type, status, stage,
            confirmation_deadline, priority, outcome_reason, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            case.ticket_id,
            case.nome_pdv,
            case.assunto,
            case.descricao_base,
            case.equipment_type.value,
            TicketStatus.TRIAGE.value,
            ConversationStage.PROXIMITY.value,
            "normal",
            "",
            now,
            now,
        ),
    )
    conn.execute(
        """
        INSERT INTO messages (ticket_id, role, content, kind, created_at)
        VALUES (?, 'assistant', ?, 'opening', ?)
        """,
        (case.ticket_id, _opening(case), now),
    )
    db._insert_ticket_events(conn, case.ticket_id, _initial_events(case))


def _case_is_complete(conn: sqlite3.Connection, case: DemoCase) -> bool:
    ticket = conn.execute(
        """
        SELECT nome_pdv, assunto, descricao_base, equipment_type
        FROM tickets
        WHERE id = ?
        """,
        (case.ticket_id,),
    ).fetchone()
    if ticket is None or tuple(ticket) != (
        case.nome_pdv,
        case.assunto,
        case.descricao_base,
        case.equipment_type.value,
    ):
        return False
    openings = conn.execute(
        """
        SELECT role, content, kind
        FROM messages
        WHERE ticket_id = ? AND kind = 'opening'
        ORDER BY id
        """,
        (case.ticket_id,),
    ).fetchall()
    first_message = conn.execute(
        """
        SELECT role, content, kind
        FROM messages
        WHERE ticket_id = ?
        ORDER BY id
        LIMIT 1
        """,
        (case.ticket_id,),
    ).fetchone()
    expected_opening = ("assistant", _opening(case), "opening")
    event_categories = conn.execute(
        """
        SELECT category
        FROM ticket_events
        WHERE ticket_id = ?
        ORDER BY id
        """,
        (case.ticket_id,),
    ).fetchall()
    return (
        len(openings) == 1
        and tuple(openings[0]) == expected_opening
        and tuple(first_message) == expected_opening
        and [category[0] for category in event_categories] == [
            TicketEventCategory.TICKET_CREATED.value,
            TicketEventCategory.SCOPE_VALIDATED.value,
            TicketEventCategory.RISK_EVALUATED.value,
        ]
    )


def seed_demo_cases() -> list[str]:
    """Atomically insert missing cases and repair incomplete demo records."""
    with db._connect() as conn:
        for case in DEMO_CASES:
            if _case_is_complete(conn, case):
                continue
            _delete_case(conn, case.ticket_id)
            _insert_case(conn, case)
    return list(DEMO_TICKET_IDS)


def reset_demo_cases() -> list[str]:
    """Atomically recreate the complete logical state for all fixed demo IDs."""
    with db._connect() as conn:
        for case in DEMO_CASES:
            _delete_case(conn, case.ticket_id)
        for case in DEMO_CASES:
            _insert_case(conn, case)
    return list(DEMO_TICKET_IDS)
