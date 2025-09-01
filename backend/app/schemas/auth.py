"""
Authentication Pydantic schemas.
"""

from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    """JWT token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data schema."""
    user_id: Optional[int] = None


class TokenRefresh(BaseModel):
    """Token refresh request schema."""
    refresh_token: str


class LoginRequest(BaseModel):
    """Login request schema."""
    email: str
    password: str


class PasswordReset(BaseModel):
    """Password reset request schema."""
    email: str


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""
    token: str
    new_password: str
