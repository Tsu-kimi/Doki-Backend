import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# Configure CORS for frontend access
# In production, set ALLOWED_ORIGINS environment variable with comma-separated domains
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add session middleware for OAuth state management
# Cloud Run injects the actual secret value via secretKeyRef
secret_key = os.getenv("SESSION_SECRET_KEY_NAME")
if not secret_key:
    # Fallback for development
    secret_key = "dev-secret-key-replace-in-production"
app.add_middleware(SessionMiddleware, secret_key=secret_key)

@app.get("/")
async def root():
    return {"message": "Doki Backend up"}

app.include_router(connectors_router, prefix="/connectors")
app.include_router(agent_router, prefix="/agent")
app.include_router(auth_router, prefix="/auth")
