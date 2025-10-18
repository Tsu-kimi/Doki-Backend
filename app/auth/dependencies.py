from typing import Any, Dict
import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.jwt_validation import validate_jwt_token, extract_user_from_jwt


def get_google_client_id() -> str:
    """Cloud Run injects the actual client ID via secretKeyRef."""
    client_id = os.getenv("GOOGLE_CLIENT_ID_NAME")
    if not client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID_NAME is not set")
    return client_id


def get_google_client_secret() -> str:
    """Cloud Run injects the actual client secret via secretKeyRef."""
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET_NAME")
    if not client_secret:
        raise RuntimeError("GOOGLE_CLIENT_SECRET_NAME is not set")
    return client_secret


def get_google_oauth_config() -> Dict[str, str]:
    return {
        "client_id": get_google_client_id(),
        "client_secret": get_google_client_secret(),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", ""),
    }


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> Dict[str, Any]:
    """
    Validate Supabase JWT token from Authorization Bearer header.
    Supports both legacy JWT secret and new Signing Keys system (HS256).
    Returns user info including user_id, email, and role.
    
    For local testing without JWT, falls back to test user if no token provided.
    """
    # Fallback for local testing without JWT (development only)
    if cred is None:
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication required",
                headers={"WWW-Authenticate": 'Bearer realm="auth_required"'},
            )
        # Development fallback to test user
        return {
            "user_id": "00000000-0000-0000-0000-000000000000",
            "email": "test@doki-mvp.local",
            "role": "authenticated",
        }
    
    # Validate JWT token using new validation utilities
    try:
        payload = validate_jwt_token(cred.credentials)
        return extract_user_from_jwt(payload)
    except jwt.exceptions.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": 'Bearer realm="auth_required"'},
        )
