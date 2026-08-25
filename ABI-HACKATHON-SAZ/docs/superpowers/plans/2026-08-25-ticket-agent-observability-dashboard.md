# Ticket Agent Observability Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a side-by-side single-ticket dashboard that displays persisted, auditable agent events through one-second incremental polling and reports the R$ 200 saving only after remote resolution.

**Architecture:** FastAPI persists safe structured events in SQLite beside each ticket transition and exposes them through an incremental REST endpoint. React keeps the existing ticket lifecycle, polls only unseen event IDs through a dedicated hook, and renders a responsive CoolCare Intelligence panel without allowing observability failures to block the chat.

**Tech Stack:** Python 3.13+, FastAPI, Pydantic, SQLite, pytest, React 19, TypeScript 6, Vite 8, Vitest, Testing Library, lucide-react.

**Spec:** `docs/superpowers/specs/2026-08-25-ticket-agent-observability-dashboard-design.md`

## Global Constraints

- Track one current ticket; do not add an aggregate dashboard.
- Use REST polling every 1,000 ms; do not add SSE, WebSocket, or a new dependency.
- Persist only safe structured metadata; never persist prompts, credentials, full user messages, stack traces, chain-of-thought, or raw model responses.
- Keep the demo saving fixed at R$ 200: potential while active, realized only for `resolvido_remotamente`, and R$ 0 for `encaminhado_fornecedor`.
- Preserve all current chat behavior, demo IDs, 30-minute confirmation timeout, urgent routing, supplier summaries, and mobile behavior.
- Keep backend-facing enum values and frontend discriminated unions identical to the spec.
- Use Portuguese user-facing copy and UTC ISO 8601 timestamps.
- Preserve unrelated changes already present in `backend/data/backend.db` and `frontend/package-lock.json`.

## File Structure

- `backend/src/models.py`: public event enums and response models.
- `backend/src/db.py`: event table, safe serialization, incremental queries, and atomic event insertion beside ticket mutations.
- `backend/src/service.py`: construction of safe domain events at existing decision points.
- `backend/src/main.py`: validated incremental events endpoint.
- `backend/src/demo_data.py`: repeatable initial demo events and event cleanup restricted to the four demo IDs.
- `backend/tests/test_ticket_events.py`: service and API behavior for the event history.
- `backend/tests/test_db.py`: persistence, ordering, filtering, validation, and atomic rollback.
- `backend/tests/test_demo_data.py`: reset isolation and repeatability for event rows.
- `frontend/src/clients/client.ts`: event contracts and endpoint client.
- `frontend/src/hooks/useTicketEvents.ts`: polling, pagination, deduplication, cancellation, terminal completion, and backoff.
- `frontend/src/hooks/useTicketEvents.test.tsx`: deterministic fake-timer hook tests.
- `frontend/src/components/AgentDashboard/AgentDashboard.tsx`: dashboard composition and safe fallback for unknown categories.
- `frontend/src/components/AgentDashboard/AgentMetrics.tsx`: stage, OCR, priority, and saving cards.
- `frontend/src/components/AgentDashboard/DecisionTimeline.tsx`: accessible chronological event list.
- `frontend/src/components/AgentDashboard/DecisionSignals.tsx`: latest safe decision metadata.
- `frontend/src/components/AgentDashboard/AgentDashboard.css`: approved Option B visual system and responsive layout.
- `frontend/src/components/AgentDashboard/AgentDashboard.test.tsx`: component states, copy, accessibility, and saving rules.
- `frontend/src/pages/Home/Home.tsx`: mount the dashboard with the current ticket.
- `frontend/src/pages/Home/Home.css`: desktop split and mobile stack while preserving the phone shell.
- `frontend/src/pages/Home/Home.test.tsx`: integrated chat/dashboard behavior.
- `frontend/src/clients/client.test.ts`: REST request and response contract.
- `README.md`: dashboard behavior and repeatable pitch instructions.

---

### Task 1: Persist safe ticket events atomically

**Files:**
- Modify: `backend/src/models.py:1`
- Modify: `backend/src/db.py:21`
- Modify: `backend/tests/test_db.py:1`

**Interfaces:**
- Produces: `TicketEventCategory`, `TicketEventState`, `TicketEventMetadataValue`, `TicketEventWrite`, `TicketEvent`, and `TicketEventsResponse` from `src.models`.
- Produces: `db.record_ticket_events(ticket_id: str, events: Collection[TicketEventWrite]) -> list[dict[str, object]]`.
- Produces: `db.list_ticket_events(ticket_id: str, after: int = 0, limit: int = 100) -> list[dict[str, object]]`.
- Changes: `db.create_ticket`, `db.set_equipment`, `db.record_checklist_actions`, and `db.set_ticket_state` accept keyword-only `events: Collection[TicketEventWrite] = ()` and persist those events in the same SQLite transaction as their existing mutation.

- [ ] **Step 1: Write failing database tests for schema, ordering, filtering, validation, and rollback**

Append these imports and tests to `backend/tests/test_db.py`:

```python
from src.models import (
    TicketEventCategory,
    TicketEventState,
    TicketEventWrite,
)


def event(category=TicketEventCategory.TICKET_CREATED, title="Chamado recebido"):
    return TicketEventWrite(
        category=category,
        title=title,
        description="Evento público e auditável.",
        state=TicketEventState.COMPLETED,
        metadata={"equipment_type": "cooler"},
    )


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
    assert remaining[0]["metadata"] == {"equipment_type": "cooler"}
    assert remaining[0]["created_at"].endswith("+00:00")


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
```

- [ ] **Step 2: Run the focused tests and verify they fail for missing event contracts**

Run:

```powershell
Set-Location backend
uv run pytest tests/test_db.py -v
```

Expected: collection fails because `TicketEventCategory`, `TicketEventState`, and `TicketEventWrite` do not exist.

- [ ] **Step 3: Add public event models with strict safe metadata validation**

Add to `backend/src/models.py`:

```python
from typing import TypeAlias

from pydantic import field_validator


class TicketEventCategory(str, Enum):
    TICKET_CREATED = "ticket_created"
    SCOPE_VALIDATED = "scope_validated"
    RISK_EVALUATED = "risk_evaluated"
    STAGE_CHANGED = "stage_changed"
    AGENT_REQUESTED = "agent_requested"
    AGENT_INTERPRETED = "agent_interpreted"
    OCR_COMPLETED = "ocr_completed"
    EQUIPMENT_CONFIRMED = "equipment_confirmed"
    TRIAGE_DECISION = "triage_decision"
    CHECKLIST_SENT = "checklist_sent"
    CONFIRMATION_WAITING = "confirmation_waiting"
    TICKET_RESOLVED = "ticket_resolved"
    SUPPLIER_ROUTED = "supplier_routed"
    CONFIRMATION_EXPIRED = "confirmation_expired"


class TicketEventState(str, Enum):
    COMPLETED = "completed"
    ACTIVE = "active"
    WAITING = "waiting"
    WARNING = "warning"
    FAILED = "failed"


TicketEventMetadataValue: TypeAlias = str | int | float | bool | None | list[str]


class TicketEventWrite(BaseModel):
    category: TicketEventCategory
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    state: TicketEventState
    metadata: dict[str, TicketEventMetadataValue] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(
        cls,
        metadata: dict[str, TicketEventMetadataValue],
    ) -> dict[str, TicketEventMetadataValue]:
        forbidden = {"prompt", "raw_response", "token", "api_key", "stack_trace", "message"}
        if forbidden.intersection(key.casefold() for key in metadata):
            raise ValueError("Metadado sensível não é permitido em eventos.")
        if any(isinstance(value, list) and not all(isinstance(item, str) for item in value) for value in metadata.values()):
            raise ValueError("Listas de metadados aceitam somente strings.")
        return metadata


class TicketEvent(TicketEventWrite):
    id: int
    ticket_id: str
    created_at: str


class TicketEventsResponse(BaseModel):
    items: list[TicketEvent]
    last_id: int
    terminal: bool
```

- [ ] **Step 4: Add the event table, index, insert helper, incremental query, and transactional mutation parameters**

In `backend/src/db.py`, import `TicketEventWrite`, create the table after `checklist_actions`, and use the same connection for each business mutation and its event rows:

```python
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
```

```python
conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_id_id "
    "ON ticket_events(ticket_id, id)"
)
```

Implement these exact helpers:

```python
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
```

Add keyword-only `events: Collection[TicketEventWrite] = ()` to `create_ticket`, `set_equipment`, `record_checklist_actions`, and `set_ticket_state`, then call `_insert_ticket_events(conn, ticket_id, events)` before each function leaves its existing `with _connect() as conn:` block. Check `cursor.rowcount` for state updates so events cannot be attached to a missing ticket.

- [ ] **Step 5: Run the database tests and verify persistence passes**

Run:

```powershell
Set-Location backend
uv run pytest tests/test_db.py -v
```

Expected: all `test_db.py` tests pass, including incremental ordering and atomic rollback.

- [ ] **Step 6: Commit the persistence layer**

```powershell
git add backend/src/models.py backend/src/db.py backend/tests/test_db.py
git commit -m "feat: persist ticket observability events"
```

---

### Task 2: Instrument the real service decision points

**Files:**
- Create: `backend/tests/test_ticket_events.py`
- Modify: `backend/src/service.py:220`

**Interfaces:**
- Consumes: `TicketEventCategory`, `TicketEventState`, `TicketEventWrite`, and transactional `events=` parameters from Task 1.
- Produces: `_event(category, title, description, state=TicketEventState.COMPLETED, **metadata) -> TicketEventWrite` inside `service.py`.
- Produces: real persisted event histories for existing ticket creation, conversation, identification, triage, timeout, resolution, and supplier-routing paths.

- [ ] **Step 1: Write failing service tests for remote, urgent, OCR, and timeout histories**

Create `backend/tests/test_ticket_events.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from src import db, service


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "events.db")
    db.init_db()


def categories(ticket_id: str) -> list[str]:
    return [str(item["category"]) for item in db.list_ticket_events(ticket_id)]


def test_remote_resolution_records_auditable_decisions(monkeypatch):
    monkeypatch.setattr(
        service.client,
        "request_conversation_reply",
        lambda payload: {"reply_key": "solicitar_identificacao", "risks": [], "symptom": "desconhecido"},
    )
    ticket = service.create_case("PDV", "Congela bebidas", "Bebidas congelando")
    ticket_id = str(ticket["id"])
    service.handle_text(ticket_id, "sim")
    service.handle_serial(ticket_id, "CX-400", "BR-1")
    service.handle_text(ticket_id, "sim, os dados estão corretos")
    service.handle_text(ticket_id, "sim, resolveu")

    history = db.list_ticket_events(ticket_id)
    assert "ticket_created" in categories(ticket_id)
    assert "risk_evaluated" in categories(ticket_id)
    assert "equipment_confirmed" in categories(ticket_id)
    assert "triage_decision" in categories(ticket_id)
    assert "checklist_sent" in categories(ticket_id)
    assert "confirmation_waiting" in categories(ticket_id)
    assert history[-1]["category"] == "ticket_resolved"
    assert history[-1]["metadata"]["saving_brl"] == 200
    assert all("message" not in item["metadata"] for item in history)


def test_critical_risk_records_warning_without_agent_request():
    ticket = service.create_case("PDV", "Cheiro de queimado", "Odor no cooler")
    history = db.list_ticket_events(str(ticket["id"]))

    assert [item["category"] for item in history][-2:] == [
        "risk_evaluated",
        "supplier_routed",
    ]
    assert history[-1]["state"] == "warning"
    assert history[-1]["metadata"]["priority"] == "urgente"
    assert "agent_requested" not in categories(str(ticket["id"]))


@pytest.mark.parametrize(
    ("confidence", "manual_required"),
    [(0.98, False), (0.79, True)],
)
def test_ocr_event_exposes_only_safe_label_fields(confidence, manual_required):
    ticket = service.create_case("PDV", "Não gela", "Cooler não refrigera")
    ticket_id = str(ticket["id"])
    service.handle_text(ticket_id, "sim")
    service.handle_label(
        ticket_id,
        {"modelo": "CX-400", "numero_serie": "BR-1", "confianca": confidence},
        "etiqueta.jpg",
    )

    ocr = next(item for item in db.list_ticket_events(ticket_id) if item["category"] == "ocr_completed")
    assert ocr["metadata"] == {
        "confidence": confidence,
        "manual_required": manual_required,
        "model": "CX-400",
        "serial": "BR-1",
    }


def test_confirmation_expiry_records_zero_saving():
    ticket = service.create_case("PDV", "Congela bebidas", "Bebidas congelando")
    ticket_id = str(ticket["id"])
    service.handle_text(ticket_id, "sim")
    service.handle_serial(ticket_id, "CX-400", "BR-1")
    waiting = service.handle_text(ticket_id, "sim, os dados estão corretos")
    deadline = datetime.fromisoformat(str(waiting["confirmation_deadline"]))

    service.expire_confirmations(deadline + timedelta(seconds=1))

    history = db.list_ticket_events(ticket_id)
    assert history[-2]["category"] == "confirmation_expired"
    assert history[-1]["category"] == "supplier_routed"
    assert history[-1]["metadata"]["saving_brl"] == 0
```

- [ ] **Step 2: Run the new service tests and verify event histories are absent**

Run:

```powershell
Set-Location backend
uv run pytest tests/test_ticket_events.py -v
```

Expected: tests fail because service operations do not pass events into the database layer.

- [ ] **Step 3: Add one safe event factory and instrument creation, agent calls, OCR, and equipment confirmation**

In `backend/src/service.py`, import the event types and add:

```python
def _event(
    category: TicketEventCategory,
    title: str,
    description: str,
    state: TicketEventState = TicketEventState.COMPLETED,
    **metadata: str | int | float | bool | None | list[str],
) -> TicketEventWrite:
    return TicketEventWrite(
        category=category,
        title=title,
        description=description,
        state=state,
        metadata=metadata,
    )
```

Pass these safe events at the corresponding existing operations:

```python
creation_events = [
    _event(TicketEventCategory.TICKET_CREATED, "Chamado recebido", "O CoolCare iniciou a triagem.", equipment_type=validated_type.value),
    _event(TicketEventCategory.RISK_EVALUATED, "Risco verificado", "A descrição inicial foi avaliada por regras de segurança.", detected=bool(risks), risk_flags=sorted(risk.value for risk in risks)),
]
if not risks:
    creation_events.insert(1, _event(TicketEventCategory.SCOPE_VALIDATED, "Escopo validado", "O equipamento está no escopo do CoolCare.", equipment_type=validated_type.value))
db.create_ticket(
    ticket_id,
    nome_pdv,
    assunto,
    descricao_base,
    validated_type,
    events=creation_events,
)
```

Before and after `client.request_conversation_reply(payload)`, record `agent_requested` and `agent_interpreted`. The interpreted metadata is exactly `reply_key`, `symptom`, and sorted `risk_flags`; do not pass `payload` or `raw_reply`.

Pass `ocr_completed` through this exact call in `handle_label`:

```python
manual_required = confianca < _OCR_CONFIDENCE_THRESHOLD or not numero_serie.strip()
db.set_equipment(
    ticket_id,
    modelo,
    numero_serie,
    confianca,
    image_name,
    events=[
        _event(
            TicketEventCategory.OCR_COMPLETED,
            "Leitura da etiqueta concluída",
            "Modelo, serial e confiança foram extraídos da etiqueta.",
            model=modelo,
            serial=numero_serie,
            confidence=confianca,
            manual_required=manual_required,
        )
    ],
)
```

Record `equipment_confirmed` only in the affirmative `EQUIPMENT_CONFIRMATION` branch, immediately before `_diagnose`.

- [ ] **Step 4: Instrument stage changes, triage decisions, checklists, waiting, resolution, supplier routing, and expiry**

For every existing `db.set_ticket_state` call, capture the source stage before the mutation and include a `stage_changed` event:

```python
_event(
    TicketEventCategory.STAGE_CHANGED,
    "Etapa atualizada",
    "O atendimento avançou para a próxima etapa.",
    from_stage=str(ticket["stage"]),
    to_stage=ConversationStage.IDENTIFICATION.value,
)
```

In `_diagnose`, persist `triage_decision` through the state change, `checklist_sent` through `record_checklist_actions`, and `confirmation_waiting` with `state=WAITING` and the ISO deadline. In positive final confirmation, persist `ticket_resolved` with `reason="confirmacao_positiva_pdv"` and `saving_brl=200`.

Extend `_route_supplier` with `extra_events: Collection[TicketEventWrite] = ()`, then persist those events plus:

```python
_event(
    TicketEventCategory.SUPPLIER_ROUTED,
    "Chamado encaminhado ao fornecedor",
    "O atendimento remoto foi encerrado e o fornecedor recebeu o encaminhamento.",
    TicketEventState.WARNING if priority == "urgente" else TicketEventState.COMPLETED,
    reason=reason,
    priority=priority,
    saving_brl=0,
)
```

For the timeout path, pass a preceding `confirmation_expired` event with `reason="sem_confirmacao_pdv"` and `priority` from the ticket. This gives deterministic order: expiration first, supplier routing second.

- [ ] **Step 5: Run service event tests and the existing backend service suites**

Run:

```powershell
Set-Location backend
uv run pytest tests/test_ticket_events.py tests/test_service.py tests/test_timeout.py tests/test_triage_rules.py -v
```

Expected: all selected tests pass and existing outcomes/messages remain unchanged.

- [ ] **Step 6: Commit real event instrumentation**

```powershell
git add backend/src/service.py backend/tests/test_ticket_events.py
git commit -m "feat: record auditable agent decisions"
```

---

### Task 3: Expose incremental events and keep demo resets repeatable

**Files:**
- Modify: `backend/src/main.py:92`
- Modify: `backend/src/demo_data.py:59`
- Modify: `backend/tests/test_api.py:20`
- Modify: `backend/tests/test_demo_data.py:120`

**Interfaces:**
- Consumes: `db.list_ticket_events`, `TicketEventsResponse`, and final ticket statuses from Tasks 1–2.
- Produces: `GET /tickets/{ticket_id}/events?after: int=0&limit: int=100 -> TicketEventsResponse`.
- Produces: repeatable initial events for `DEMO-REMOTE`, `DEMO-DOOR`, `DEMO-SUPPLIER`, and `DEMO-URGENT`.

- [ ] **Step 1: Write failing API contract tests**

Append to `backend/tests/test_api.py`:

```python
def test_ticket_events_endpoint_is_incremental_and_terminal(api):
    created = api.post(
        "/tickets",
        json={
            "nome_pdv": "Bar do João",
            "assunto": "Cheiro de queimado",
            "descricao_base": "Odor no cooler",
            "equipment_type": "cooler",
        },
    ).json()

    first = api.get(f"/tickets/{created['id']}/events", params={"limit": 1})
    assert first.status_code == 200
    assert len(first.json()["items"]) == 1
    assert first.json()["terminal"] is True

    after = first.json()["last_id"]
    second = api.get(
        f"/tickets/{created['id']}/events",
        params={"after": after, "limit": 100},
    )
    assert second.status_code == 200
    assert all(item["id"] > after for item in second.json()["items"])
    assert second.json()["last_id"] >= after


@pytest.mark.parametrize("query", ["after=-1", "limit=0", "limit=201"])
def test_ticket_events_endpoint_validates_bounds(api, query):
    assert api.get(f"/tickets/T-1/events?{query}").status_code == 422


def test_ticket_events_endpoint_returns_404_for_missing_ticket(api):
    assert api.get("/tickets/missing/events").status_code == 404
```

- [ ] **Step 2: Write a failing demo-reset isolation test**

Append to `backend/tests/test_demo_data.py`:

```python
def test_demo_reset_recreates_demo_events_without_touching_real_events(api):
    real = api.post(
        "/tickets",
        json={
            "nome_pdv": "PDV real",
            "assunto": "Não gela",
            "descricao_base": "Cooler sem refrigeração",
            "equipment_type": "cooler",
        },
    ).json()
    before = api.get(f"/tickets/{real['id']}/events").json()["items"]

    assert api.post("/demo/reset").status_code == 200
    first_demo = api.get("/tickets/DEMO-REMOTE/events").json()["items"]
    assert api.post("/demo/reset").status_code == 200
    second_demo = api.get("/tickets/DEMO-REMOTE/events").json()["items"]

    assert [item["category"] for item in first_demo] == [
        "ticket_created",
        "scope_validated",
        "risk_evaluated",
    ]
    assert [item["category"] for item in second_demo] == [
        "ticket_created",
        "scope_validated",
        "risk_evaluated",
    ]
    assert api.get(f"/tickets/{real['id']}/events").json()["items"] == before
```

- [ ] **Step 3: Run the endpoint and demo tests and verify route/reset failures**

Run:

```powershell
Set-Location backend
uv run pytest tests/test_api.py tests/test_demo_data.py -v
```

Expected: new endpoint tests fail with 404/405 and demo histories are absent.

- [ ] **Step 4: Implement the validated endpoint**

In `backend/src/main.py`, import `Query` and `TicketEventsResponse`, then add directly after `get_ticket`:

```python
@app.get("/tickets/{ticket_id}/events", response_model=TicketEventsResponse)
def get_ticket_events(
    ticket_id: str,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> TicketEventsResponse:
    ticket = _ticket_or_404(ticket_id)
    items = db.list_ticket_events(ticket_id, after=after, limit=limit)
    last_id = int(items[-1]["id"]) if items else after
    return TicketEventsResponse.model_validate({
        "items": items,
        "last_id": last_id,
        "terminal": ticket["status"] in {
            TicketStatus.REMOTE_RESOLVED.value,
            TicketStatus.SUPPLIER.value,
        },
    })
```

- [ ] **Step 5: Make demo deletion and insertion event-aware**

In `backend/src/demo_data.py`, delete `ticket_events` before deleting each demo ticket:

```python
conn.execute("DELETE FROM ticket_events WHERE ticket_id = ?", (ticket_id,))
```

After inserting each demo ticket, insert the three initial events with the same titles, descriptions, states, and metadata used by `service.create_case`: `ticket_created`, `scope_validated`, and a non-detected `risk_evaluated`. Use `db._insert_ticket_events(conn, case.ticket_id, events)` so the reset remains one transaction.

Extend `_case_is_complete` to require exactly those three ordered categories in addition to the opening message. This makes seeding repair an old demo record that has no observability history.

- [ ] **Step 6: Run API, demo, and full backend tests**

Run:

```powershell
Set-Location backend
uv run pytest -v
```

Expected: the entire backend suite passes, including API bounds and repeatable demo isolation.

- [ ] **Step 7: Commit the endpoint and demo lifecycle**

```powershell
git add backend/src/main.py backend/src/demo_data.py backend/tests/test_api.py backend/tests/test_demo_data.py
git commit -m "feat: expose incremental ticket events"
```

---

### Task 4: Add the frontend event client and resilient polling hook

**Files:**
- Modify: `frontend/src/clients/client.ts:79`
- Modify: `frontend/src/clients/client.test.ts:1`
- Create: `frontend/src/hooks/useTicketEvents.ts`
- Create: `frontend/src/hooks/useTicketEvents.test.tsx`

**Interfaces:**
- Produces: `TicketEventCategory`, `TicketEventState`, `TicketEventMetadataValue`, `TicketEvent`, and `TicketEventsResponse` TypeScript contracts.
- Produces: `getTicketEvents(ticketId: string, after?: number, limit?: number) -> Promise<TicketEventsResponse>`.
- Produces: `useTicketEvents(ticketId: string | null) -> { events: TicketEvent[]; connection: EventConnection; error: string | null }`, where `EventConnection = 'idle' | 'loading' | 'active' | 'reconnecting' | 'complete'`.

- [ ] **Step 1: Write the failing client contract test**

Add `getTicketEvents` to the import in `frontend/src/clients/client.test.ts` and append:

```typescript
test('gets only ticket events after the supplied id', async () => {
  const payload = {
    items: [{
      id: 8,
      ticket_id: 'T-1',
      category: 'risk_evaluated',
      title: 'Risco verificado',
      description: 'Nenhum risco crítico detectado.',
      state: 'completed',
      metadata: { detected: false, risk_flags: [] },
      created_at: '2026-08-25T17:32:09Z',
    }],
    last_id: 8,
    terminal: false,
  }
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(payload), { status: 200 }),
  )

  await expect(getTicketEvents('T-1', 7, 100)).resolves.toEqual(payload)
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining('/tickets/T-1/events?after=7&limit=100'),
  )
})
```

- [ ] **Step 2: Add TypeScript contracts and the REST client**

Add exact unions and interfaces to `frontend/src/clients/client.ts`:

```typescript
export type TicketEventCategory =
  | 'ticket_created' | 'scope_validated' | 'risk_evaluated' | 'stage_changed'
  | 'agent_requested' | 'agent_interpreted' | 'ocr_completed'
  | 'equipment_confirmed' | 'triage_decision' | 'checklist_sent'
  | 'confirmation_waiting' | 'ticket_resolved' | 'supplier_routed'
  | 'confirmation_expired'

export type TicketEventState = 'completed' | 'active' | 'waiting' | 'warning' | 'failed'
export type TicketEventMetadataValue = string | number | boolean | null | string[]

export interface TicketEvent {
  id: number
  ticket_id: string
  category: TicketEventCategory
  title: string
  description: string
  state: TicketEventState
  metadata: Record<string, TicketEventMetadataValue>
  created_at: string
}

export interface TicketEventsResponse {
  items: TicketEvent[]
  last_id: number
  terminal: boolean
}
```

Implement:

```typescript
export async function getTicketEvents(
  ticketId: string,
  after = 0,
  limit = 100,
): Promise<TicketEventsResponse> {
  const params = new URLSearchParams({ after: String(after), limit: String(limit) })
  const response = await request(
    `${API_BASE_URL}/tickets/${ticketId}/events?${params}`,
    undefined,
    'Não foi possível acompanhar o agente',
  )
  return readResponse(response, 'Não foi possível acompanhar o agente')
}
```

- [ ] **Step 3: Write failing fake-timer hook tests for incremental polling, no concurrency, terminal completion, pagination, and backoff**

Create `frontend/src/hooks/useTicketEvents.test.tsx` using `renderHook` and a hoisted mock for `getTicketEvents`. Include these tests:

```typescript
test('polls incrementally without concurrent requests and stops when terminal', async () => {
  vi.useFakeTimers()
  let finishSecond: ((value: TicketEventsResponse) => void) | undefined
  client.getTicketEvents
    .mockResolvedValueOnce({ items: [event(1)], last_id: 1, terminal: false })
    .mockImplementationOnce(() => new Promise((resolve) => { finishSecond = resolve }))

  const { result } = renderHook(() => useTicketEvents('T-1'))
  await act(async () => undefined)
  expect(client.getTicketEvents).toHaveBeenNthCalledWith(1, 'T-1', 0, 100)

  await act(async () => { vi.advanceTimersByTime(1_000) })
  expect(client.getTicketEvents).toHaveBeenNthCalledWith(2, 'T-1', 1, 100)
  await act(async () => { vi.advanceTimersByTime(3_000) })
  expect(client.getTicketEvents).toHaveBeenCalledTimes(2)

  await act(async () => {
    finishSecond?.({ items: [event(2)], last_id: 2, terminal: true })
  })
  await act(async () => { vi.advanceTimersByTime(5_000) })
  expect(client.getTicketEvents).toHaveBeenCalledTimes(2)
  expect(result.current.events.map((item) => item.id)).toEqual([1, 2])
  expect(result.current.connection).toBe('complete')
})
```

```typescript
test('drains a full page immediately and deduplicates ids', async () => {
  vi.useFakeTimers()
  const fullPage = Array.from({ length: 100 }, (_, index) => event(index + 1))
  client.getTicketEvents
    .mockResolvedValueOnce({ items: fullPage, last_id: 100, terminal: false })
    .mockResolvedValueOnce({ items: [event(100), event(101)], last_id: 101, terminal: false })

  const { result } = renderHook(() => useTicketEvents('T-1'))
  await act(async () => undefined)

  expect(client.getTicketEvents).toHaveBeenNthCalledWith(2, 'T-1', 100, 100)
  expect(result.current.events).toHaveLength(101)
})
```

```typescript
test('keeps events and backs off at one, two, four, then five seconds', async () => {
  vi.useFakeTimers()
  client.getTicketEvents
    .mockResolvedValueOnce({ items: [event(1)], last_id: 1, terminal: false })
    .mockRejectedValueOnce(new Error('offline'))
    .mockRejectedValueOnce(new Error('offline'))
    .mockRejectedValueOnce(new Error('offline'))
    .mockResolvedValueOnce({ items: [event(2)], last_id: 2, terminal: false })

  const { result } = renderHook(() => useTicketEvents('T-1'))
  await act(async () => undefined)
  for (const delay of [1_000, 1_000, 2_000, 4_000]) {
    await act(async () => { vi.advanceTimersByTime(delay) })
  }

  expect(result.current.events.map((item) => item.id)).toEqual([1, 2])
  expect(result.current.connection).toBe('active')
})
```

Define `event(id: number): TicketEvent` in the test with category `ticket_created`, completed state, empty metadata, and a fixed UTC timestamp. Reset timers and mocks after every test.

- [ ] **Step 4: Run hook tests and verify the hook is missing**

Run:

```powershell
Set-Location frontend
npm test -- src/hooks/useTicketEvents.test.tsx src/clients/client.test.ts
```

Expected: hook test collection fails because `useTicketEvents.ts` does not exist.

- [ ] **Step 5: Implement the polling state machine**

Create `frontend/src/hooks/useTicketEvents.ts` with:

```typescript
import { useEffect, useState } from 'react'
import { getTicketEvents, type TicketEvent } from '../clients/client'

export type EventConnection = 'idle' | 'loading' | 'active' | 'reconnecting' | 'complete'

export interface TicketEventsState {
  events: TicketEvent[]
  connection: EventConnection
  error: string | null
}

const PAGE_LIMIT = 100
const POLL_MS = 1_000
const RETRY_MS = [1_000, 2_000, 4_000, 5_000] as const

export function useTicketEvents(ticketId: string | null): TicketEventsState {
  const [state, setState] = useState<TicketEventsState>({
    events: [],
    connection: ticketId ? 'loading' : 'idle',
    error: null,
  })

  useEffect(() => {
    let active = true
    let inFlight = false
    let lastId = 0
    let failures = 0
    let timer: number | undefined

    setState({ events: [], connection: ticketId ? 'loading' : 'idle', error: null })
    if (!ticketId) return () => { active = false }

    const schedule = (delay: number) => {
      timer = window.setTimeout(() => { void poll() }, delay)
    }

    const poll = async () => {
      if (!active || inFlight) return
      inFlight = true
      try {
        const response = await getTicketEvents(ticketId, lastId, PAGE_LIMIT)
        if (!active) return
        lastId = Math.max(lastId, response.last_id)
        failures = 0
        setState((current) => {
          const byId = new Map(current.events.map((item) => [item.id, item]))
          response.items.forEach((item) => byId.set(item.id, item))
          return {
            events: [...byId.values()].sort((left, right) => left.id - right.id),
            connection: response.terminal ? 'complete' : 'active',
            error: null,
          }
        })
        if (response.items.length === PAGE_LIMIT) schedule(0)
        else if (!response.terminal) schedule(POLL_MS)
      } catch {
        if (!active) return
        const delay = RETRY_MS[Math.min(failures, RETRY_MS.length - 1)]
        failures += 1
        setState((current) => ({
          ...current,
          connection: 'reconnecting',
          error: 'Acompanhamento temporariamente indisponível.',
        }))
        schedule(delay)
      } finally {
        inFlight = false
      }
    }

    void poll()
    return () => {
      active = false
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [ticketId])

  return state
}
```

Keep `schedule(0)` as the full-page branch shown above. Because it uses `window.setTimeout`, the callback runs only after the current promise continuation reaches `finally` and resets `inFlight`; keep exactly one live timer.

- [ ] **Step 6: Run client and hook tests**

Run:

```powershell
Set-Location frontend
npm test -- src/hooks/useTicketEvents.test.tsx src/clients/client.test.ts
```

Expected: both files pass; fake timers prove incremental IDs, pagination, terminal stop, and bounded backoff.

- [ ] **Step 7: Commit the frontend event transport**

```powershell
git add frontend/src/clients/client.ts frontend/src/clients/client.test.ts frontend/src/hooks/useTicketEvents.ts frontend/src/hooks/useTicketEvents.test.tsx
git commit -m "feat: poll incremental ticket events"
```

---

### Task 5: Build the approved Option B dashboard components

**Files:**
- Create: `frontend/src/components/AgentDashboard/AgentDashboard.tsx`
- Create: `frontend/src/components/AgentDashboard/AgentMetrics.tsx`
- Create: `frontend/src/components/AgentDashboard/DecisionTimeline.tsx`
- Create: `frontend/src/components/AgentDashboard/DecisionSignals.tsx`
- Create: `frontend/src/components/AgentDashboard/AgentDashboard.css`
- Create: `frontend/src/components/AgentDashboard/AgentDashboard.test.tsx`

**Interfaces:**
- Consumes: `Ticket`, `TicketEvent`, and `EventConnection` from Tasks 1 and 4.
- Produces: `AgentDashboard({ ticket, events, connection }: { ticket: Ticket; events: TicketEvent[]; connection: EventConnection })`.
- Produces: pure `savingPresentation(status: TicketStatus) -> { label: string; value: string; note: string; tone: 'potential' | 'realized' | 'lost' }` exported for direct testing.

- [ ] **Step 1: Write failing component tests for metrics, timeline, fallback, accessibility, and saving rules**

Create `frontend/src/components/AgentDashboard/AgentDashboard.test.tsx` with fixtures and these assertions:

```typescript
test.each([
  ['em_triagem', 'Economia potencial', 'R$ 200', 'Ainda não contabilizada'],
  ['aguardando_confirmacao', 'Economia potencial', 'R$ 200', 'Ainda não contabilizada'],
  ['resolvido_remotamente', 'Economia realizada', 'R$ 200', 'Visita técnica evitada'],
  ['encaminhado_fornecedor', 'Economia não realizada', 'R$ 0', 'Atendimento encaminhado'],
] as const)('derives saving only from status %s', (status, label, value, note) => {
  expect(savingPresentation(status)).toMatchObject({ label, value, note })
})


test('renders decision focus, safe signals, and chronological events', () => {
  render(<AgentDashboard ticket={waitingTicket} events={[event(2), event(1)]} connection="active" />)

  expect(screen.getByRole('region', { name: 'Inteligência do agente' })).toBeInTheDocument()
  expect(screen.getByText('Agente ativo')).toBeInTheDocument()
  expect(screen.getByRole('list', { name: 'Linha do tempo do agente' })).toHaveTextContent('Chamado recebido')
  expect(screen.getByText('congela_bebidas')).toBeInTheDocument()
  expect(screen.getByText('R$ 200')).toBeInTheDocument()
})


test('keeps known event copy for an unknown future category', () => {
  const future = { ...event(3), category: 'future_event' as TicketEvent['category'], title: 'Nova etapa', description: 'Evento compatível.' }
  render(<AgentDashboard ticket={waitingTicket} events={[future]} connection="active" />)

  expect(screen.getByText('Nova etapa')).toBeInTheDocument()
  expect(screen.getByText('Evento compatível.')).toBeInTheDocument()
})


test('shows reconnecting without removing the last events', () => {
  render(<AgentDashboard ticket={waitingTicket} events={[event(1)]} connection="reconnecting" />)
  expect(screen.getByText('Reconectando')).toBeInTheDocument()
  expect(screen.getByText('Chamado recebido')).toBeInTheDocument()
})
```

The `waitingTicket` fixture includes stage `aguardando_confirmacao`, normal priority, equipment confidence `0.96`, and model/serial `CX-400`/`BR-DEMO-001`. The `event` fixture includes a `triage_decision` with safe symptom, outcome, and priority metadata.

- [ ] **Step 2: Run the component test and verify missing modules**

Run:

```powershell
Set-Location frontend
npm test -- src/components/AgentDashboard/AgentDashboard.test.tsx
```

Expected: collection fails because the dashboard modules do not exist.

- [ ] **Step 3: Implement pure metrics and saving presentation**

In `AgentMetrics.tsx`, define the exact status mapping:

```typescript
export function savingPresentation(status: TicketStatus): SavingPresentation {
  if (status === 'resolvido_remotamente') {
    return { label: 'Economia realizada', value: 'R$ 200', note: 'Visita técnica evitada', tone: 'realized' }
  }
  if (status === 'encaminhado_fornecedor') {
    return { label: 'Economia não realizada', value: 'R$ 0', note: 'Atendimento encaminhado', tone: 'lost' }
  }
  return { label: 'Economia potencial', value: 'R$ 200', note: 'Ainda não contabilizada', tone: 'potential' }
}
```

Map the six conversation stages to `1/5`, `2/5`, `2/5`, `3/5`, `4/5`, and `5/5`. Render OCR as a rounded percentage when equipment exists and `—` otherwise. Render the API priority verbatim as `Normal` or `Urgente`.

- [ ] **Step 4: Implement timeline, signals, and dashboard composition**

`DecisionTimeline` sorts a copied event array by ID, renders a semantic `<ol aria-label="Linha do tempo do agente">`, preserves API title/description for unknown categories, and formats timestamps with `Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })`.

`DecisionSignals` scans events from newest to oldest and extracts only these keys when their runtime types are strings/booleans/numbers: `symptom`, `detected`, `model`, `serial`, `outcome`, and `priority`. It falls back to the current ticket equipment, priority, and outcome reason.

`AgentDashboard` renders:

```tsx
<aside className="agent-dashboard" aria-label="Inteligência do agente">
  <header className="agent-dashboard-header">
    <div><strong>CoolCare Intelligence</strong><span>{ticket.id}</span></div>
    <span className={`connection connection-${connection}`}>{connectionLabel[connection]}</span>
  </header>
  <AgentMetrics ticket={ticket} />
  {events.length === 0 ? (
    <p className="agent-empty">Preparando acompanhamento do agente...</p>
  ) : (
    <div className="agent-dashboard-grid">
      <DecisionTimeline events={events} />
      <DecisionSignals ticket={ticket} events={events} />
    </div>
  )}
</aside>
```

Connection labels are `Preparando`, `Agente ativo`, `Reconectando`, and `Atendimento concluído`; `idle` and `loading` both use `Preparando`.

- [ ] **Step 5: Implement the approved visual system and responsive component styles**

In `AgentDashboard.css`, use existing CSS variables from `index.css`. Implement a white card surface, `var(--green-950)` header, four metric cards, a highlighted saving card, a two-column decision grid, state dots with text labels, and `@media (max-width: 900px)` to collapse the decision grid. Add `@media (prefers-reduced-motion: reduce)` to remove pulsing from the active indicator.

Use these stable layout selectors:

```css
.agent-metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }
.agent-dashboard-grid { display:grid; grid-template-columns:minmax(0,1.15fr) minmax(230px,.85fr); gap:12px; }
@media (max-width: 900px) {
  .agent-metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .agent-dashboard-grid { grid-template-columns:1fr; }
}
```

- [ ] **Step 6: Run component tests, lint, and TypeScript build**

Run:

```powershell
Set-Location frontend
npm test -- src/components/AgentDashboard/AgentDashboard.test.tsx
npm run lint
npm run build
```

Expected: component tests pass, ESLint reports no errors, and TypeScript/Vite build succeeds.

- [ ] **Step 7: Commit the dashboard components**

```powershell
git add frontend/src/components/AgentDashboard
git commit -m "feat: build agent intelligence dashboard"
```

---

### Task 6: Integrate dashboard with the live ticket and verify the pitch journeys

**Files:**
- Modify: `frontend/src/pages/Home/Home.tsx:99`
- Modify: `frontend/src/pages/Home/Home.css:1`
- Modify: `frontend/src/pages/Home/Home.test.tsx:1`
- Modify: `README.md:1`

**Interfaces:**
- Consumes: `useTicketEvents(ticket?.id ?? null)` and `AgentDashboard` from Tasks 4–5.
- Produces: desktop side-by-side chat/dashboard presentation and mobile chat-then-dashboard stack.

- [ ] **Step 1: Extend the Home client mock and write failing integration tests**

Add `getTicketEvents: vi.fn()` to the hoisted client mock in `Home.test.tsx`, and default it in `beforeEach`:

```typescript
client.getTicketEvents.mockResolvedValue({ items: [], last_id: 0, terminal: false })
```

Append:

```typescript
test('shows the live chat beside the agent dashboard for the same ticket', async () => {
  client.getTicket.mockResolvedValue(ticket())
  client.getTicketEvents.mockResolvedValue({
    items: [{
      id: 1,
      ticket_id: 'T-1',
      category: 'ticket_created',
      title: 'Chamado recebido',
      description: 'O CoolCare iniciou a triagem.',
      state: 'completed',
      metadata: { equipment_type: 'cooler' },
      created_at: createdAt,
    }],
    last_id: 1,
    terminal: false,
  })

  render(<Home />)

  const experience = await screen.findByLabelText('Experiência do chamado')
  expect(experience).toHaveClass('case-experience')
  expect(screen.getByLabelText('Atendimento CoolCare')).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Inteligência do agente' })).toBeInTheDocument()
  expect(await screen.findByText('Chamado recebido')).toBeInTheDocument()
  expect(client.getTicketEvents).toHaveBeenCalledWith('T-1', 0, 100)
})
```

```typescript
test('keeps the chat usable while agent-event polling reconnects', async () => {
  vi.useFakeTimers()
  client.getTicket.mockResolvedValue(ticket())
  client.getTicketEvents.mockRejectedValue(new Error('offline'))

  render(<Home />)
  await act(async () => undefined)

  expect(screen.getByText('Reconectando')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /^sim$/i })).toBeEnabled()
})
```

- [ ] **Step 2: Run Home tests and verify the dashboard is absent**

Run:

```powershell
Set-Location frontend
npm test -- src/pages/Home/Home.test.tsx
```

Expected: new tests fail because Home does not render `AgentDashboard` or call `getTicketEvents`.

- [ ] **Step 3: Integrate the hook and dashboard without coupling chat errors to polling errors**

In `Home.tsx`, import `AgentDashboard` and `useTicketEvents`, then call:

```typescript
const eventState = useTicketEvents(ticket?.id ?? null)
```

Move the existing `<section className="phone-shell phone-shell-flex" aria-label="Atendimento CoolCare">` node unchanged inside a new `<main className="case-experience" aria-label="Experiência do chamado">`. Add this dashboard sibling immediately after that section and close the new `main` before the existing outer `.home` div closes:

```tsx
{ticket && (
  <AgentDashboard
    ticket={ticket}
    events={eventState.events}
    connection={eventState.connection}
  />
)}
```

Do not copy `eventState.error` into Home's existing `error`; the dashboard connection state owns polling failures.

- [ ] **Step 4: Change only the page-level layout needed for desktop split and mobile stack**

In `Home.css`, replace the single centered phone layout with:

```css
.case-experience {
  display: grid;
  grid-template-columns: minmax(360px, 520px) minmax(520px, 1fr);
  gap: 20px;
  width: min(1440px, 100%);
  min-height: calc(100svh - 56px);
  margin: 0 auto;
}

.phone-shell {
  height: calc(100svh - 56px);
  margin: 0;
}

@media (max-width: 1040px) {
  .case-experience { grid-template-columns: 1fr; }
  .phone-shell { width:100%; max-width:720px; margin:0 auto; }
  .agent-dashboard { width:100%; max-width:720px; margin:0 auto; }
}
```

Keep the existing `max-width: 720px` full-viewport phone treatment, but allow the dashboard to follow below it instead of forcing `.home` to clip at one viewport height.

- [ ] **Step 5: Document how to present the live dashboard**

Add a `Dashboard do agente` section to `README.md` after service startup. State that the right panel polls `GET /tickets/{id}/events` every second, that refreshing reconstructs the history, and that the R$ 200 card is potential until positive confirmation. Extend the repeatable demo notes:

```text
DEMO-REMOTE: acompanhe risco, identificação, checklist, confirmação e a mudança para Economia realizada — R$ 200.
DEMO-URGENT: acompanhe a interrupção por risco, prioridade urgente e Economia não realizada — R$ 0.
```

- [ ] **Step 6: Run the integrated frontend suite and production checks**

Run:

```powershell
Set-Location frontend
npm test
npm run lint
npm run build
```

Expected: all frontend tests pass, lint reports no errors, and the Vite production build succeeds.

- [ ] **Step 7: Run the complete backend and agent regression suites**

Run:

```powershell
Set-Location ../backend
uv run pytest -v
Set-Location ../agent
uv run pytest tests -v
```

Expected: all backend and agent tests pass; agent tests do not require live credentials.

- [ ] **Step 8: Perform the two acceptance journeys against local services**

Start services in three terminals as documented in `README.md`, reset the demo, and exercise `DEMO-REMOTE` and `DEMO-URGENT`. Verify in the browser:

```text
DEMO-REMOTE
- chat and panel reference the same ticket ID;
- each backend transition appears once and in chronological order;
- the active card says Economia potencial — R$ 200;
- after “sim, resolveu”, polling stops and the card says Economia realizada — R$ 200.

DEMO-URGENT
- risk_evaluated is followed by supplier_routed;
- priority is Urgente and the timeline uses warning presentation;
- polling stops and the card says Economia não realizada — R$ 0.

Responsive
- at 1440 px chat and dashboard are side by side;
- below 1040 px the dashboard follows the chat;
- no horizontal scrollbar appears at 390 px;
- keyboard focus and visible labels remain available.
```

- [ ] **Step 9: Commit the integrated experience and documentation**

```powershell
git add frontend/src/pages/Home/Home.tsx frontend/src/pages/Home/Home.css frontend/src/pages/Home/Home.test.tsx README.md
git commit -m "feat: integrate live agent dashboard"
```

---

## Final Verification

- [ ] Run `git status --short` and confirm only pre-existing user changes remain outside the six task commits.
- [ ] Run `Set-Location backend; uv run pytest -v` and record the passing test count.
- [ ] Run `Set-Location ../agent; uv run pytest tests -v` and record the passing test count.
- [ ] Run `Set-Location ../frontend; npm test; npm run lint; npm run build` and record each successful command.
- [ ] Compare the implementation against all ten acceptance criteria in the spec before claiming completion.
