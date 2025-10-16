from fastapi import FastAPI
from app.api.connectors import router as connectors_router
from app.api.agent import router as agent_router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Doki Backend")

@app.get("/")
async def root():
    return {"message": "Doki Backend up"}

app.include_router(connectors_router, prefix="/connectors")
app.include_router(agent_router, prefix="/agent")
