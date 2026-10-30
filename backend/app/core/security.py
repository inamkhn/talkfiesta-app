"""Password hashing, access-token signing and refresh-token primitives.

Password hashes use argon2id (no bcrypt-style truncation limit), but the
password *length* is still capped by the request schema to bound hashing cost.
Refresh tokens are opaque: only their SHA-256 digest is persisted, so a database
leak does not yield usable credentials.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

ACCESS_TOKEN_TYPE = "access"

_hasher = PasswordHash.recommended()
# Verified against when the account is missing or has no password, so the
# failure path costs the same as a real verification (timing-based enumeration).
_DUMMY_HASH = _hasher.hash("talkfiesta-dummy-password-never-used")


def hash_password(password: str) -> str:
    """Return an argon2id hash suitable for ``users.hashed_password``."""

    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Constant-ish time check; returns ``False`` for malformed stored hashes."""

    try:
        return _hasher.verify(password, hashed_password)
    except (UnknownHashError, ValueError):
        return False


def burn_password_verification(password: str) -> None:
    """Spend the same work as a real verification for unknown accounts."""

    verify_password(password, _DUMMY_HASH)


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Decoded, validated access-token payload."""

    user_id: uuid.UUID
    role: str
    token_version: int
    jti: str
    expires_at: datetime


def create_access_token(
    *,
    user_id: uuid.UUID,
    role: str,
    token_version: int,
    now: datetime | None = None,
) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)`` for the given account state."""

    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "tv": token_version,
        "type": ACCESS_TOKEN_TYPE,
        "jti": str(uuid.uuid4()),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, settings.jwt_algorithm)
    return token, settings.access_token_ttl_minutes * 60


def decode_access_token(token: str) -> AccessTokenClaims:
    """Validate signature/expiry and return typed claims."""

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("The access token is invalid or has expired.") from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("The access token is invalid or has expired.")

    try:
        user_id = uuid.UUID(payload["sub"])
        token_version = int(payload.get("tv", 0))
    except (KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("The access token is invalid or has expired.") from exc

    return AccessTokenClaims(
        user_id=user_id,
        role=str(payload.get("role", "LEARNER")),
        token_version=token_version,
        jti=str(payload["jti"]),
        expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
    )


def new_refresh_token() -> tuple[str, uuid.UUID]:
    """Return ``(opaque_token, jti)``; only the digest is persisted."""

    jti = uuid.uuid4()
    return f"{jti}.{secrets.token_urlsafe(32)}", jti


def hash_refresh_token(token: str) -> str:
    """Return the SHA-256 hex digest used as the ``auth_sessions`` lookup key."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry(now: datetime | None = None) -> datetime:
    """Absolute expiry for a newly issued refresh token."""

    return (now or datetime.now(UTC)) + timedelta(days=settings.refresh_token_ttl_days)
