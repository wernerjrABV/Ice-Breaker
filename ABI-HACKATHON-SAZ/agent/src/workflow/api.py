from typing import Any
from fastapi import FastAPI
from workflow.main import kickoff

app = FastAPI()


@app.post("/kickoff")
def run_kickoff(inputs: dict[str, Any]) -> Any:
    return kickoff(inputs)


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
