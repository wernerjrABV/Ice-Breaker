import base64
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import requests
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from src import client, db, demo_data, service
from src.client import call_agent_kickoff
from src.models import EquipmentType, TicketEventsResponse, TicketResponse, TicketStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateTicketRequest(BaseModel):
    nome_pdv: str
    assunto: str
    descricao_base: str = ""
    equipment_type: EquipmentType = EquipmentType.COOLER

    @field_validator("equipment_type", mode="before")
    @classmethod
    def validate_equipment_type(cls, value: object) -> EquipmentType:
        try:
            return EquipmentType(str(value).strip().casefold())
        except ValueError as exc:
            raise ValueError(
                "O tipo de equipamento deve ser cooler ou geladeira."
            ) from exc


class CreateDemoTicketRequest(BaseModel):
    assunto: str = Field(min_length=1, max_length=500)

    @field_validator("assunto")
    @classmethod
    def strip_subject(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("O assunto é obrigatório.")
        return value


class MessageRequest(BaseModel):
    content: str


class SerialRequest(BaseModel):
    modelo: str = ""
    numero_serie: str


def _ticket_or_404(ticket_id: str) -> dict[str, Any]:
    ticket = db.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")
    return ticket


def _present_ticket(ticket: dict[str, Any]) -> TicketResponse:
    payload = dict(ticket)
    payload["supplier_summary"] = (
        service.supplier_summary(str(ticket["id"]))
        if ticket["status"] == TicketStatus.SUPPLIER.value
        else None
    )
    return TicketResponse.model_validate(payload)


@app.post("/tickets", status_code=201, response_model=TicketResponse)
def create_ticket(request: CreateTicketRequest) -> TicketResponse:
    try:
        return _present_ticket(
            service.create_case(
                request.nome_pdv,
                request.assunto,
                request.descricao_base,
                request.equipment_type,
            )
        )
    except service.EquipmentScopeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/demo/tickets", status_code=201, response_model=TicketResponse)
def create_demo_ticket(request: CreateDemoTicketRequest) -> TicketResponse:
    return _present_ticket(service.create_demo_case(request.assunto))


@app.get("/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: str) -> TicketResponse:
    return _present_ticket(_ticket_or_404(ticket_id))


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


@app.post("/tickets/{ticket_id}/messages", response_model=TicketResponse)
def post_message(ticket_id: str, request: MessageRequest) -> TicketResponse:
    _ticket_or_404(ticket_id)
    try:
        return _present_ticket(service.handle_text(ticket_id, request.content))
    except service.EquipmentScopeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except service.InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.AgentResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao consultar a API do agente: {exc}",
        ) from exc


@app.post("/tickets/{ticket_id}/equipment/serial", response_model=TicketResponse)
def post_serial(ticket_id: str, request: SerialRequest) -> TicketResponse:
    _ticket_or_404(ticket_id)
    try:
        return _present_ticket(
            service.handle_serial(ticket_id, request.modelo, request.numero_serie)
        )
    except service.EquipmentScopeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except service.InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tickets/{ticket_id}/equipment/photo", response_model=TicketResponse)
async def post_photo(
    ticket_id: str,
    photo: UploadFile = File(...),
) -> TicketResponse:
    _ticket_or_404(ticket_id)
    try:
        service.require_identification(ticket_id)
    except service.InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    image_bytes = await photo.read()
    media_type = photo.content_type or "application/octet-stream"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    image_data_url = f"data:{media_type};base64,{encoded}"
    try:
        label = client.read_equipment_label(image_data_url)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao consultar a API do agente: {exc}",
        ) from exc
    try:
        return _present_ticket(service.handle_label(ticket_id, label, photo.filename))
    except service.EquipmentScopeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/maintenance/expire-confirmations")
def expire_confirmations(now: datetime | None = None) -> list[str]:
    if now is not None and os.getenv("DEMO_MODE", "").casefold() != "true":
        raise HTTPException(
            status_code=403,
            detail="O parâmetro now só é aceito quando DEMO_MODE=true.",
        )
    if now is not None:
        return service.expire_confirmations(now, demo_data.DEMO_TICKET_IDS)
    return service.expire_confirmations()


@app.post("/demo/reset")
def reset_demo() -> list[str]:
    return demo_data.reset_demo_cases()


@app.post("/kickoff")
def kickoff(inputs: dict[str, Any]) -> Any:
    try:
        return call_agent_kickoff(inputs)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao consultar a API do agente: {exc}",
        ) from exc


@app.post("/kickoff/async", status_code=202)
def kickoff_async(inputs: dict[str, Any], background_tasks: BackgroundTasks) -> dict[str, str]:
    request_id = str(uuid.uuid4())
    db.create_request(request_id, inputs)
    background_tasks.add_task(_run_async_kickoff, request_id, inputs)
    return {"id": request_id}


@app.get("/kickoff/async")
def kickoff_async_list() -> list[dict[str, Any]]:
    return db.list_requests()


@app.get("/kickoff/async/{request_id}")
def kickoff_async_status(request_id: str) -> dict[str, Any]:
    record = db.get_request(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    return record


def _run_async_kickoff(request_id: str, inputs: dict[str, Any]) -> None:
    try:
        result = call_agent_kickoff(inputs)
        db.update_request(request_id, "completed", result=result)
    except requests.RequestException as exc:
        db.update_request(request_id, "failed", error=str(exc))


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
