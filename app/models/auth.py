"""
Pydantic models for authentication requests and responses.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    """Request to sign up a new user with email and password."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=6, description="User's password (min 6 characters)")
    display_name: str = Field(..., min_length=1, description="User's display name")


class SignInRequest(BaseModel):
    """Request to sign in with email and password."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class AuthResponse(BaseModel):
    """Response after successful authentication."""
    status: str = Field(..., description="Authentication status")
    access_token: str = Field(..., description="Supabase JWT access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token for renewing access")
    user: dict = Field(..., description="User information")
    message: str = Field(..., description="Human-readable message")


class SignOutRequest(BaseModel):
    """Request to sign out (requires JWT in Authorization header)."""
    pass  # No body needed, JWT comes from header


class SignOutResponse(BaseModel):
    """Response after sign out."""
    status: str
    message: str
