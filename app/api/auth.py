import os
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from app.auth.dependencies import get_google_oauth_config, get_current_user
from app.connectors.supabase import get_supabase_client
from app.core.encryption import encrypt_token_for_storage
from app.models.auth import SignUpRequest, SignInRequest, AuthResponse, SignOutResponse

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


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignUpRequest):
    """
    Sign up a new user with email, password, and display name.
    
    Creates user in Supabase Auth and stores display_name in user metadata.
    Returns JWT token for immediate authentication.
    """
    supabase = get_supabase_client()
    
    try:
        # Sign up with Supabase Auth
        # Store display_name in user metadata
        auth_response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {
                    "display_name": request.display_name,
                }
            }
        })
    except Exception as e:
        error_msg = str(e)
        # Check for common errors
        if "already registered" in error_msg.lower() or "already exists" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=500, detail=f"Signup failed: {error_msg}")
    
    # Check if user was created
    if not auth_response.user:
        raise HTTPException(
            status_code=500,
            detail="Signup failed: No user returned from Supabase"
        )
    
    # Check if email confirmation is required
    if not auth_response.session:
        return {
            "status": "pending_confirmation",
            "access_token": "",
            "refresh_token": None,
            "user": {
                "id": auth_response.user.id,
                "email": auth_response.user.email,
                "display_name": request.display_name,
            },
            "message": "Signup successful! Please check your email to confirm your account."
        }
    
    # User is immediately authenticated (email confirmation disabled)
    return {
        "status": "authenticated",
        "access_token": auth_response.session.access_token,
        "refresh_token": auth_response.session.refresh_token,
        "user": {
            "id": auth_response.user.id,
            "email": auth_response.user.email,
            "display_name": request.display_name,
        },
        "message": "Signup successful! You are now logged in."
    }


@router.post("/signin", response_model=AuthResponse)
async def signin(request: SignInRequest):
    """
    Sign in with email and password.
    
    Returns JWT token for authenticated requests.
    """
    supabase = get_supabase_client()
    
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })
    except Exception as e:
        error_msg = str(e).lower()
        # Check for common errors
        if "invalid" in error_msg or "credentials" in error_msg:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if "not confirmed" in error_msg or "email not confirmed" in error_msg:
            raise HTTPException(status_code=403, detail="Please confirm your email before signing in")
        raise HTTPException(status_code=500, detail=f"Sign in failed: {str(e)}")
    
    # Verify authentication succeeded
    if not auth_response.user or not auth_response.session:
        raise HTTPException(
            status_code=401,
            detail="Sign in failed: Invalid credentials"
        )
    
    # Extract display_name from user metadata
    user_metadata = auth_response.user.user_metadata or {}
    display_name = user_metadata.get("display_name", "")
    
    return {
        "status": "authenticated",
        "access_token": auth_response.session.access_token,
        "refresh_token": auth_response.session.refresh_token,
        "user": {
            "id": auth_response.user.id,
            "email": auth_response.user.email,
            "display_name": display_name,
        },
        "message": "Sign in successful!"
    }


@router.post("/signout", response_model=SignOutResponse)
async def signout(current_user: dict = Depends(get_current_user)):
    """
    Sign out the current user.
    
    Requires valid JWT token in Authorization header.
    Invalidates the current session.
    """
    supabase = get_supabase_client()
    
    try:
        supabase.auth.sign_out()
    except Exception as e:
        # Log error but don't fail - token is already validated
        print(f"Warning: Sign out error: {str(e)}")
    
    return {
        "status": "signed_out",
        "message": "Successfully signed out"
    }
