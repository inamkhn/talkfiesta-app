"""Purpose-scoped email tokens bound to database state for single use."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.modules.auth.models import User

ActionPurpose = Literal["password_reset", "email_verification"]


def invalid_action_token() -> UnauthorizedError:
    return UnauthorizedError(
        "This link is invalid or has expired.", code="INVALID_ACTION_TOKEN"
    )


def create_action_token(user: User, purpose: ActionPurpose) -> str:
    minutes = (
        settings.password_reset_ttl_minutes
        if purpose == "password_reset"
        else settings.email_verification_ttl_minutes
    )
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "tv": user.token_version,
            "type": purpose,
            "aud": f"talkfiesta:{purpose}",
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + timedelta(minutes=minutes),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_action_token(token: str, purpose: ActionPurpose) -> dict:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=f"talkfiesta:{purpose}",
            options={
                "require": ["sub", "email", "tv", "type", "aud", "jti", "iat", "exp"]
            },
        )
        if claims["type"] != purpose or type(claims["tv"]) is not int:
            raise invalid_action_token()
        uuid.UUID(claims["sub"])
        return claims
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise invalid_action_token() from exc
