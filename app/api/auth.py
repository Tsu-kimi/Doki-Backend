import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from app.auth.dependencies import get_google_oauth_config
from app.connectors.supabase import get_supabase_client
from app.core.encryption import encrypt_token_for_storage

router = APIRouter()

# OpenID scope is required to get ID token for Supabase Auth
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.readonly",  # Required to list spreadsheets
    "https://www.googleapis.com/auth/spreadsheets.readonly",  # Required to read spreadsheet data
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
async def google_callback(request: Request):
    """
    OAuth callback that:
    1. Exchanges authorization code for Google tokens (including ID token)
    2. Signs in/creates user in Supabase Auth using Google ID token
    3. Stores Google OAuth tokens linked to real Supabase user
    4. Returns Supabase JWT token for subsequent API calls
    """
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
    
    # Get ID token for Supabase Auth (requires openid scope)
    id_token = credentials.id_token
    if not id_token:
        raise HTTPException(
            status_code=500,
            detail="ID token not found in OAuth response. Ensure 'openid' scope is requested."
        )
    
    # Extract granted scopes
    granted_scopes = list(credentials.granted_scopes) if credentials.granted_scopes else []

    # Authenticate with Supabase using Google ID token
    # This creates the user in Supabase Auth if they don't exist
    supabase = get_supabase_client()
    try:
        auth_response = supabase.auth.sign_in_with_id_token({
            "provider": "google",
            "token": id_token,
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to authenticate with Supabase: {str(e)}"
        )
    
    # Extract Supabase user info and JWT token
    if not auth_response.user or not auth_response.session:
        raise HTTPException(
            status_code=500,
            detail="Supabase authentication failed: No user or session returned"
        )
    
    supabase_user_id = auth_response.user.id
    supabase_jwt = auth_response.session.access_token
    
    # Store Google OAuth tokens linked to real Supabase user
    # Note: Supabase client requires JSON-serializable values, so we use base64 encoding
    credentials_data = {
        "user_id": supabase_user_id,
        "provider": "google",
        "access_token_encrypted": encrypt_token_for_storage(access_token),
        "refresh_token_encrypted": encrypt_token_for_storage(refresh_token) if refresh_token else None,
        "expires_at": token_expiry,
        "scopes": granted_scopes,
    }
    try:
        supabase.table("credentials").insert(credentials_data).execute()
    except Exception as e:
        # Log error but don't fail the auth flow
        print(f"Warning: Failed to store Google credentials: {str(e)}")

    return {
        "status": "authenticated",
        "access_token": supabase_jwt,
        "user": {
            "id": auth_response.user.id,
            "email": auth_response.user.email,
        },
        "message": "Successfully authenticated with Supabase. Use the access_token for API requests."
    }
