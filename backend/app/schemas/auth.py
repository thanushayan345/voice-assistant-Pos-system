"""Authentication request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=100)
    email: Optional[str] = Field(default=None, max_length=120)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="owner")

    @field_validator("username")
    @classmethod
    def clean_username(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned or " " in cleaned:
            raise ValueError("Username must not contain spaces.")
        return cleaned

    @field_validator("email")
    @classmethod
    def clean_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if not cleaned:
            return None
        if "@" not in cleaned:
            raise ValueError("Invalid email address.")
        return cleaned

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in ("owner", "staff"):
            raise ValueError("Role must be 'owner' or 'staff'.")
        return cleaned


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
