from fastapi import APIRouter
from app.models.agent import InterpretRequest, InterpretResponse

router = APIRouter()


@router.post("/interpret", response_model=InterpretResponse)
async def interpret(req: InterpretRequest):
    return InterpretResponse(plan="stub", steps=[])
