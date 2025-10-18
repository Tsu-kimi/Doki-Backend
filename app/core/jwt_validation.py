"""
JWT validation utilities for Supabase Auth tokens.

Supports both legacy JWT secret (HS256) and new Signing Keys system.
The new system allows key rotation without downtime.
"""
import os
import jwt
import httpx
from typing import Dict, Any, Optional
from functools import lru_cache


@lru_cache(maxsize=1)
def get_jwt_secret() -> str:
    """
    Get Supabase JWT secret for HS256 token validation.
    Cloud Run injects the actual secret value via secretKeyRef.
    
    This works with both:
    - Legacy JWT secret system
    - New Signing Keys system (when using HS256 symmetric keys)
    """
    secret = os.getenv("SUPABASE_JWT_SECRET_NAME")
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET_NAME is not set in environment")
    return secret


async def get_jwks(supabase_url: str) -> Dict[str, Any]:
    """
    Fetch JSON Web Key Set (JWKS) from Supabase for asymmetric key validation.
    
    This enables support for ES256 and RS256 algorithms in the new Signing Keys system.
    Currently not used but prepared for future asymmetric key support.
    
    Args:
        supabase_url: Your Supabase project URL
        
    Returns:
        JWKS containing public keys for JWT verification
    """
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        return response.json()


def validate_jwt_token(
    token: str,
    audience: str = "authenticated",
    algorithms: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Validate Supabase JWT token using HS256 algorithm.
    
    Args:
        token: JWT token string
        audience: Expected audience claim (default: "authenticated")
        algorithms: List of allowed algorithms (default: ["HS256"])
        
    Returns:
        Decoded JWT payload with user claims
        
    Raises:
        jwt.exceptions.PyJWTError: If token is invalid or expired
    """
    if algorithms is None:
        algorithms = ["HS256"]
    
    jwt_secret = get_jwt_secret()
    payload = jwt.decode(
        token,
        jwt_secret,
        audience=audience,
        algorithms=algorithms,
    )
    
    return payload


def extract_user_from_jwt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract user information from decoded JWT payload.
    
    Args:
        payload: Decoded JWT payload
        
    Returns:
        Dictionary with user_id, email, role, and phone
    """
    return {
        "user_id": payload.get("sub"),  # 'sub' claim contains user UUID
        "email": payload.get("email"),
        "role": payload.get("role", "authenticated"),
        "phone": payload.get("phone"),
    }
