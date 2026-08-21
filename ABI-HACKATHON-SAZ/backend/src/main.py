import base64
import uuid
from contextlib import asynccontextmanager
from typing import Any

import requests
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src import client, db, service
from src.client import call_agent_kickoff


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


class MessageRequest(BaseModel):
    content: str


class SerialRequest(BaseModel):
    modelo: str = ""
    numero_serie: str


def _ticket_or_404(ticket_id: str) -> dict[str, Any]:
    ticket = db.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.post("/tickets", status_code=201)
def create_ticket(request: CreateTicketRequest) -> dict[str, Any]:
    return service.create_case(request.nome_pdv, request.assunto, request.descricao_base)


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str) -> dict[str, Any]:
    return _ticket_or_404(ticket_id)


@app.post("/tickets/{ticket_id}/messages")
def post_message(ticket_id: str, request: MessageRequest) -> dict[str, Any]:
    _ticket_or_404(ticket_id)
    try:
        return service.handle_text(ticket_id, request.content)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Agent API call failed: {exc}") from exc


@app.post("/tickets/{ticket_id}/equipment/serial")
def post_serial(ticket_id: str, request: SerialRequest) -> dict[str, Any]:
    _ticket_or_404(ticket_id)
    try:
        return service.handle_serial(ticket_id, request.modelo, request.numero_serie)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tickets/{ticket_id}/equipment/photo")
async def post_photo(
    ticket_id: str,
    photo: UploadFile = File(...),
) -> dict[str, Any]:
    _ticket_or_404(ticket_id)
    image_bytes = await photo.read()
    media_type = photo.content_type or "application/octet-stream"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    image_data_url = f"data:{media_type};base64,{encoded}"
    try:
        label = client.read_equipment_label(image_data_url)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Agent API call failed: {exc}") from exc
    return service.handle_label(ticket_id, label, photo.filename)


@app.post("/maintenance/expire-confirmations")
def expire_confirmations() -> list[dict[str, Any]]:
    return service.expire_confirmations()


@app.post("/kickoff")
def kickoff(inputs: dict[str, Any]) -> Any:
    try:
        return call_agent_kickoff(inputs)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Agent API call failed: {exc}") from exc


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
        raise HTTPException(status_code=404, detail="Request not found")
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
