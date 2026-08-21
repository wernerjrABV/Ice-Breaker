import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ConversationStage, TicketStatus

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


def _as_utc(value: datetime) -> datetime:
    """Return a datetime normalized to UTC for consistent persistence/comparison."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _datetime_iso(value: datetime | None) -> str | None:
    return _as_utc(value).isoformat() if value is not None else None


def create_ticket(ticket_id: str, nome_pdv: str, assunto: str, descricao_base: str) -> None:
    now = _now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tickets (
                id, nome_pdv, assunto, descricao_base, status, stage,
                confirmation_deadline, priority, outcome_reason, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                nome_pdv,
                assunto,
                descricao_base,
                TicketStatus.TRIAGE.value,
                ConversationStage.PROXIMITY.value,
                "normal",
                "",
                now,
                now,
            ),
        )


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


def set_ticket_state(
    ticket_id: str,
    status: TicketStatus,
    stage: ConversationStage,
    deadline: datetime | None = None,
    priority: str = "normal",
    reason: str = "",
) -> None:
    with _connect() as conn:
        conn.execute(
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
    return {
        "id": row["id"],
        "nome_pdv": row["nome_pdv"],
        "assunto": row["assunto"],
        "descricao_base": row["descricao_base"],
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
    }


def get_ticket(ticket_id: str) -> dict[str, object] | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return None
        return _ticket_from_row(conn, row)


def list_expired_confirmations(now: datetime | None = None) -> list[dict[str, object]]:
    current = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM tickets
            WHERE status = ?
              AND stage = ?
              AND confirmation_deadline IS NOT NULL
            ORDER BY confirmation_deadline, id
            """,
            (
                TicketStatus.WAITING_CONFIRMATION.value,
                ConversationStage.CONFIRMATION.value,
            ),
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
