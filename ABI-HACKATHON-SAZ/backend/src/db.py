import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "backend.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
