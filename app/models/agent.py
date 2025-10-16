from pydantic import BaseModel
from typing import List


class InterpretRequest(BaseModel):
    prompt: str


class InterpretResponse(BaseModel):
    plan: str
    steps: List[str] = []
