import os
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from app.api.connectors import router as connectors_router
from app.api.agent import router as agent_router
from app.api.auth import router as auth_router
from dotenv import load_dotenv

load_dotenv()

# DEVELOPMENT ONLY: Allow OAuth over HTTP for local testing
# WARNING: Never enable this in production - Cloud Run will use HTTPS
if os.getenv("ENVIRONMENT") != "production":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app = FastAPI(title="Doki Backend")

# Add session middleware for OAuth state management
secret_key = os.getenv("SESSION_SECRET_KEY", "dev-secret-key-replace-in-production")
app.add_middleware(SessionMiddleware, secret_key=secret_key)

@app.get("/")
async def root():
    return {"message": "Doki Backend up"}

app.include_router(connectors_router, prefix="/connectors")
app.include_router(agent_router, prefix="/agent")
app.include_router(auth_router, prefix="/auth")
