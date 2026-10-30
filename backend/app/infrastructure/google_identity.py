"""Verify Google ID tokens locally using Google's rotating public keys."""

from dataclasses import dataclass
from functools import lru_cache

import jwt
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError, UnauthorizedError


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    name: str | None
    authoritative_email: bool


@lru_cache
def google_keys() -> jwt.PyJWKClient:
    return jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", timeout=10)


def verify_google_token(token: str) -> GoogleIdentity:
    if not settings.google_client_id:
        raise ServiceUnavailableError("Google sign-in is not configured.")
    try:
        key = google_keys().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=["accounts.google.com", "https://accounts.google.com"],
            options={
                "require": [
                    "sub",
                    "email",
                    "email_verified",
                    "iss",
                    "aud",
                    "iat",
                    "exp",
                ]
            },
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise ValueError("Invalid subject")
        if claims["email_verified"] is not True:
            raise ValueError("Unverified email")
        if claims.get("azp", settings.google_client_id) != settings.google_client_id:
            raise ValueError("Invalid authorized party")
        email = str(TypeAdapter(EmailStr).validate_python(claims["email"])).lower()
        name = claims.get("name")
        return GoogleIdentity(
            subject=subject,
            email=email,
            name=name.strip()[:100] or None if isinstance(name, str) else None,
            authoritative_email=email.endswith("@gmail.com") or bool(claims.get("hd")),
        )
    except jwt.PyJWKClientConnectionError as exc:
        raise ServiceUnavailableError(
            "Google sign-in is temporarily unavailable."
        ) from exc
    except (jwt.PyJWTError, ValueError, TypeError, ValidationError) as exc:
        raise UnauthorizedError(
            "The Google ID token is invalid or expired.", code="INVALID_GOOGLE_TOKEN"
        ) from exc
