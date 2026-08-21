from typing import Any
from fastapi import FastAPI
from workflow.contracts import ConversationReply, ConversationRequest, EquipmentLabel, LabelReadRequest
from workflow.conversation import generate_reply
from workflow.label_reader import read_label
from workflow.main import kickoff

app = FastAPI()


@app.post("/kickoff")
def run_kickoff(inputs: dict[str, Any]) -> Any:
    return kickoff(inputs)


@app.post("/label/read", response_model=EquipmentLabel)
def label_read(request: LabelReadRequest) -> EquipmentLabel:
    return read_label(request.image_data_url)


@app.post("/conversation/respond", response_model=ConversationReply)
def conversation_respond(request: ConversationRequest) -> ConversationReply:
    return generate_reply(request)


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
