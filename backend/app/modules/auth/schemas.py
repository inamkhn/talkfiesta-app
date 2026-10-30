"""Request and response contracts for the auth endpoints."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Password bounds live here so they show up in the OpenAPI contract. argon2id
# has no bcrypt-style 72-byte truncation, but the cap still bounds hashing cost.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


class RegisterRequest(BaseModel):
    """``POST /auth/register`` body.

    Server-owned fields (``user_id``, ``role``, ``is_active``, ``cefr``) are
    rejected by ``extra="forbid"``. Whitespace is trimmed from the email and
    name only — never from the password.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )
    first_name: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        # Accounts are stored lowercased; ix_users_email_lower backs the match.
        return value.strip().lower()

    @field_validator("first_name")
    @classmethod
    def _blank_name_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LoginRequest(BaseModel):
    """``POST /auth/login`` body.

    No minimum password length here: login must not reveal password rules, and
    the length cap only bounds hashing cost.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserSummary(BaseModel):
    """Public view of the account returned to its owner."""

    id: UUID
    email: str
    first_name: str | None
    roles: list[str]
    onboarding_completed: bool


class RegisterResponse(BaseModel):
    """``201 Created`` body; the refresh token travels in an HttpOnly cookie."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserSummary


class LoginResponse(RegisterResponse):
    """``200 OK`` body; the refresh token travels in an HttpOnly cookie."""


class EmailActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class ActionTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1, max_length=4096)


class ResetPasswordRequest(ActionTokenRequest):
    new_password: str = Field(
        min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


class GoogleExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str = Field(min_length=1, max_length=8192)


class MessageResponse(BaseModel):
    message: str
