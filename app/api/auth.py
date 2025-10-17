import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from app.auth.dependencies import get_google_oauth_config, get_current_user
from app.connectors.supabase import get_supabase_client
from app.core.encryption import encrypt_token

router = APIRouter()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def _build_flow(config: dict, redirect_uri: str) -> Flow:
    client_config = {
        "web": {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uris": [redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config=client_config, scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    return flow


@router.get("/google/login")
async def google_login(request: Request):
    config = get_google_oauth_config()
    redirect_uri = config.get("redirect_uri") or ""
    if not redirect_uri:
        raise HTTPException(status_code=500, detail="GOOGLE_REDIRECT_URI is not configured")
    flow = _build_flow(config, redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    # Store state in session for verification in callback
    request.session["oauth_state"] = state
    return RedirectResponse(url=authorization_url)


@router.get("/google/callback")
async def google_callback(request: Request, user=Depends(get_current_user)):
    # Retrieve state from session
    stored_state = request.session.get("oauth_state")
    if not stored_state:
        raise HTTPException(status_code=400, detail="Missing OAuth state. Please restart the login flow.")
    
    config = get_google_oauth_config()
    redirect_uri = config.get("redirect_uri") or ""
    if not redirect_uri:
        raise HTTPException(status_code=500, detail="GOOGLE_REDIRECT_URI is not configured")
    
    # Rebuild flow with stored state for verification
    client_config = {
        "web": {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uris": [redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config=client_config, scopes=SCOPES, state=stored_state)
    flow.redirect_uri = redirect_uri
    
    try:
        flow.fetch_token(authorization_response=str(request.url))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to exchange code for tokens: {str(e)}") from e
    
    # Clear state from session after successful exchange
    request.session.pop("oauth_state", None)

    credentials = flow.credentials
    access_token = credentials.token
    refresh_token = credentials.refresh_token or ""
    token_expiry = credentials.expiry.isoformat() if credentials.expiry else None
    
    # Extract granted scopes
    granted_scopes = list(credentials.granted_scopes) if credentials.granted_scopes else []

    supabase = get_supabase_client()
    data = {
        "user_id": user.get("user_id", "stub"),
        "provider": "google",
        "access_token_encrypted": encrypt_token(access_token).hex(),
        "refresh_token_encrypted": encrypt_token(refresh_token).hex() if refresh_token else None,
        "expires_at": token_expiry,
        "scopes": granted_scopes,
    }
    try:
        supabase.table("credentials").insert(data).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store credentials: {str(e)}")

    return {"status": "ok"}
