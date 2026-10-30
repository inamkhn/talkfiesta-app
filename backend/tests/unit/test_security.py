"""Unit tests for hashing and token primitives (no database needed)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    burn_password_verification,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_token_expiry,
    verify_password,
)


def test_hash_is_salted_and_verifiable() -> None:
    first = hash_password("correct horse battery")
    second = hash_password("correct horse battery")

    assert first != second  # distinct salt per hash
    assert first != "correct horse battery"
    assert verify_password("correct horse battery", first)
    assert not verify_password("wrong password", first)


def test_malformed_hash_returns_false_instead_of_raising() -> None:
    assert verify_password("anything", "not-a-valid-hash") is False


def test_dummy_verification_never_raises() -> None:
    burn_password_verification("anything")


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()

    token, expires_in = create_access_token(
        user_id=user_id, role="LEARNER", token_version=3
    )
    claims = decode_access_token(token)

    assert claims.user_id == user_id
    assert claims.role == "LEARNER"
    assert claims.token_version == 3
    assert claims.expires_at > datetime.now(UTC)
    assert expires_in == settings.access_token_ttl_minutes * 60


def test_token_signed_with_another_secret_is_rejected() -> None:
    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "jti": "forged",
            "iat": 0,
            "exp": 9999999999,
        },
        "not-the-app-secret-but-long-enough-for-hs256",
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError):
        decode_access_token(forged)


def test_expired_token_is_rejected() -> None:
    token, _ = create_access_token(
        user_id=uuid.uuid4(),
        role="LEARNER",
        token_version=0,
        now=datetime.now(UTC) - timedelta(hours=1),
    )

    with pytest.raises(UnauthorizedError):
        decode_access_token(token)


def test_refresh_tokens_are_opaque_and_stably_hashed() -> None:
    token, jti = new_refresh_token()
    digest = hash_refresh_token(token)

    assert token.startswith(f"{jti}.")
    assert len(digest) == 64
    assert digest == hash_refresh_token(token)
    assert token not in digest
    assert hash_refresh_token(new_refresh_token()[0]) != digest


def test_refresh_expiry_uses_configured_days() -> None:
    now = datetime.now(UTC)

    assert (refresh_token_expiry(now) - now).days == settings.refresh_token_ttl_days
