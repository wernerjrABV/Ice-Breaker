import json
import sqlite3
from collections.abc import Collection
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ConversationStage, EquipmentType, TicketEventWrite, TicketStatus

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "backend.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kickoff_requests (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                input TEXT,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                nome_pdv TEXT NOT NULL,
                assunto TEXT NOT NULL,
                descricao_base TEXT NOT NULL,
                equipment_type TEXT NOT NULL DEFAULT 'cooler',
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
        ticket_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(tickets)").fetchall()
        }
        if "equipment_type" not in ticket_columns:
            conn.execute(
                "ALTER TABLE tickets ADD COLUMN "
                "equipment_type TEXT NOT NULL DEFAULT 'cooler'"
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                kind TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS equipment (
                ticket_id TEXT PRIMARY KEY,
                modelo TEXT NOT NULL,
                numero_serie TEXT NOT NULL,
                confianca REAL NOT NULL,
                image_name TEXT,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checklist_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                state TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_id_id "
            "ON ticket_events(ticket_id, id)"
        )


def _as_utc(value: datetime) -> datetime:
    """Return a datetime normalized to UTC for consistent persistence/comparison."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _datetime_iso(value: datetime | None) -> str | None:
    return _as_utc(value).isoformat() if value is not None else None


def _insert_ticket_events(
    conn: sqlite3.Connection,
    ticket_id: str,
    events: Collection[TicketEventWrite],
) -> list[dict[str, object]]:
    inserted: list[dict[str, object]] = []
    for event in events:
        created_at = _now_iso()
        cursor = conn.execute(
            """
            INSERT INTO ticket_events (
                ticket_id, category, title, description, state, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                event.category.value,
                event.title,
                event.description,
                event.state.value,
                json.dumps(event.metadata, ensure_ascii=False, sort_keys=True),
                created_at,
            ),
        )
        inserted.append({
            "id": int(cursor.lastrowid),
            "ticket_id": ticket_id,
            "category": event.category.value,
            "title": event.title,
            "description": event.description,
            "state": event.state.value,
            "metadata": event.metadata,
            "created_at": created_at,
        })
    return inserted


def record_ticket_events(
    ticket_id: str,
    events: Collection[TicketEventWrite],
) -> list[dict[str, object]]:
    with _connect() as conn:
        return _insert_ticket_events(conn, ticket_id, events)


def list_ticket_events(
    ticket_id: str,
    after: int = 0,
    limit: int = 100,
) -> list[dict[str, object]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, ticket_id, category, title, description, state,
                   metadata_json, created_at
            FROM ticket_events
            WHERE ticket_id = ? AND id > ?
            ORDER BY id
            LIMIT ?
            """,
            (ticket_id, after, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "ticket_id": row["ticket_id"],
            "category": row["category"],
            "title": row["title"],
            "description": row["description"],
            "state": row["state"],
            "metadata": json.loads(row["metadata_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def create_ticket(
    ticket_id: str,
    nome_pdv: str,
    assunto: str,
    descricao_base: str,
    equipment_type: EquipmentType = EquipmentType.COOLER,
    *,
    events: Collection[TicketEventWrite] = (),
) -> None:
    now = _now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tickets (
                id, nome_pdv, assunto, descricao_base, equipment_type, status, stage,
                confirmation_deadline, priority, outcome_reason, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                nome_pdv,
                assunto,
                descricao_base,
                equipment_type.value,
                TicketStatus.TRIAGE.value,
                ConversationStage.PROXIMITY.value,
                "normal",
                "",
                now,
                now,
            ),
        )
        _insert_ticket_events(conn, ticket_id, events)


def append_message(ticket_id: str, role: str, content: str, kind: str = "text") -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO messages (ticket_id, role, content, kind, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ticket_id, role, content, kind, _now_iso()),
        )
        conn.execute(
            "UPDATE tickets SET updated_at = ? WHERE id = ?",
            (_now_iso(), ticket_id),
        )


def set_equipment(
    ticket_id: str,
    modelo: str,
    numero_serie: str,
    confianca: float,
    image_name: str | None,
    *,
    events: Collection[TicketEventWrite] = (),
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO equipment (ticket_id, modelo, numero_serie, confianca, image_name)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ticket_id) DO UPDATE SET
                modelo = excluded.modelo,
                numero_serie = excluded.numero_serie,
                confianca = excluded.confianca,
                image_name = excluded.image_name
            """,
            (ticket_id, modelo, numero_serie, confianca, image_name),
        )
        conn.execute(
            "UPDATE tickets SET updated_at = ? WHERE id = ?",
            (_now_iso(), ticket_id),
        )
        _insert_ticket_events(conn, ticket_id, events)


def record_checklist_actions(
    ticket_id: str,
    actions: Collection[str],
    *,
    events: Collection[TicketEventWrite] = (),
) -> None:
    """Persist each backend-approved checklist action as structured evidence."""
    safe_actions = tuple(str(action).strip() for action in actions if str(action).strip())
    now = _now_iso()
    with _connect() as conn:
        conn.execute(
            "DELETE FROM checklist_actions WHERE ticket_id = ?",
            (ticket_id,),
        )
        conn.executemany(
            """
            INSERT INTO checklist_actions (ticket_id, content, created_at)
            VALUES (?, ?, ?)
            """,
            ((ticket_id, action, now) for action in safe_actions),
        )
        conn.execute(
            "UPDATE tickets SET updated_at = ? WHERE id = ?",
            (now, ticket_id),
        )
        _insert_ticket_events(conn, ticket_id, events)


def set_ticket_state(
    ticket_id: str,
    status: TicketStatus,
    stage: ConversationStage,
    deadline: datetime | None = None,
    priority: str = "normal",
    reason: str = "",
    *,
    events: Collection[TicketEventWrite] = (),
) -> None:
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE tickets
            SET status = ?, stage = ?, confirmation_deadline = ?, priority = ?,
                outcome_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status.value,
                stage.value,
                _datetime_iso(deadline),
                priority,
                reason,
                _now_iso(),
                ticket_id,
            ),
        )
        if cursor.rowcount:
            _insert_ticket_events(conn, ticket_id, events)


def _ticket_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    equipment_row = conn.execute(
        "SELECT modelo, numero_serie, confianca, image_name FROM equipment WHERE ticket_id = ?",
        (row["id"],),
    ).fetchone()
    messages = conn.execute(
        """
        SELECT role, content, kind, created_at
        FROM messages
        WHERE ticket_id = ?
        ORDER BY id
        """,
        (row["id"],),
    ).fetchall()
    checklist_actions = conn.execute(
        """
        SELECT content
        FROM checklist_actions
        WHERE ticket_id = ?
        ORDER BY id
        """,
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "nome_pdv": row["nome_pdv"],
        "assunto": row["assunto"],
        "descricao_base": row["descricao_base"],
        "equipment_type": row["equipment_type"],
        "status": row["status"],
        "stage": row["stage"],
        "confirmation_deadline": row["confirmation_deadline"],
        "priority": row["priority"],
        "outcome_reason": row["outcome_reason"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "equipment": (
            {
                "modelo": equipment_row["modelo"],
                "numero_serie": equipment_row["numero_serie"],
                "confianca": equipment_row["confianca"],
                "image_name": equipment_row["image_name"],
            }
            if equipment_row is not None
            else None
        ),
        "messages": [
            {
                "role": message["role"],
                "content": message["content"],
                "kind": message["kind"],
                "created_at": message["created_at"],
            }
            for message in messages
        ],
        "checklist_actions": [action["content"] for action in checklist_actions],
    }


def get_ticket(ticket_id: str) -> dict[str, object] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return None
        return _ticket_from_row(conn, row)


def list_expired_confirmations(
    now: datetime | None = None,
    ticket_ids: Collection[str] | None = None,
) -> list[dict[str, object]]:
    """Return only confirmation-stage tickets whose UTC deadline has elapsed."""
    current = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    if isinstance(ticket_ids, str):
        exact_ids = (ticket_ids,)
    else:
        exact_ids = tuple(ticket_ids) if ticket_ids is not None else None
    if exact_ids == ():
        return []
    id_filter = ""
    params: list[str] = [
        TicketStatus.WAITING_CONFIRMATION.value,
        ConversationStage.CONFIRMATION.value,
    ]
    if exact_ids is not None:
        placeholders = ", ".join("?" for _ in exact_ids)
        id_filter = f" AND id IN ({placeholders})"
        params.extend(exact_ids)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM tickets
            WHERE status = ?
              AND stage = ?
              AND confirmation_deadline IS NOT NULL
              {id_filter}
            ORDER BY confirmation_deadline, id
            """,
            params,
        ).fetchall()
        expired = []
        for row in rows:
            deadline = datetime.fromisoformat(row["confirmation_deadline"])
            if _as_utc(deadline) <= current:
                expired.append(_ticket_from_row(conn, row))
        return expired


def create_request(request_id: str, inputs: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO kickoff_requests (id, status, input, result, error, created_at, updated_at)
            VALUES (?, 'pending', ?, NULL, NULL, ?, ?)
            """,
            (request_id, json.dumps(inputs), now, now),
        )


def update_request(request_id: str, status: str, result: Any = None, error: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE kickoff_requests
            SET status = ?, result = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, json.dumps(result) if result is not None else None, error, now, request_id),
        )


def list_requests() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM kickoff_requests ORDER BY created_at"
        ).fetchall()

    return [
        {
            "id": row["id"],
            "status": row["status"],
            "input": json.loads(row["input"]) if row["input"] is not None else None,
            "result": json.loads(row["result"]) if row["result"] is not None else None,
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def get_request(request_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM kickoff_requests WHERE id = ?", (request_id,)
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "status": row["status"],
        "input": json.loads(row["input"]) if row["input"] is not None else None,
        "result": json.loads(row["result"]) if row["result"] is not None else None,
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
