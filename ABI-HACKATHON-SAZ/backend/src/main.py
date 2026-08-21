import uuid
from contextlib import asynccontextmanager
from typing import Any

import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src import db
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
