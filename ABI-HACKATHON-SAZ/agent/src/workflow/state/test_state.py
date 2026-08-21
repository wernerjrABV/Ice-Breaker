from pydantic import BaseModel

class TestState(BaseModel):
    subject: str = "AbInbev"
    result: str = ""