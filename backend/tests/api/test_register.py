"""API contract tests for ``POST /api/v1/auth/register``."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import decode_access_token, hash_refresh_token
from app.modules.auth.models import AuthSession, User

REGISTER_URL = "/api/v1/auth/register"
VALID_BODY = {"email": "Sam@Example.com", "password": "supersecret123"}


async def test_register_creates_account_and_session(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await client.post(
        REGISTER_URL, json={**VALID_BODY, "first_name": "Sam"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["user"]["email"] == "sam@example.com"
    assert body["user"]["first_name"] == "Sam"
    assert body["user"]["roles"] == ["LEARNER"]
    assert body["user"]["onboarding_completed"] is False
    assert response.headers["Location"] == "/api/v1/users/me"
    assert response.headers["X-Request-ID"].startswith("req_")

    cookie_header = response.headers["set-cookie"]
    assert "HttpOnly" in cookie_header
    assert "Path=/api/v1/auth" in cookie_header
    refresh_token = response.cookies.get("tf_refresh")
    assert refresh_token

    claims = decode_access_token(body["access_token"])
    assert str(claims.user_id) == body["user"]["id"]
    assert claims.role == "LEARNER"

    async with session_factory() as session:
        user = (await session.execute(select(User))).scalar_one()
        stored_session = (await session.execute(select(AuthSession))).scalar_one()

    assert user.email == "sam@example.com"
    assert user.hashed_password is not None
    assert user.hashed_password != VALID_BODY["password"]
    assert user.is_active is True
    assert user.token_version == 0
    assert user.email_verified_at is None

    assert stored_session.user_id == user.id
    assert stored_session.revoked_at is None
    assert stored_session.revoked_reason is None
    assert stored_session.token_hash == hash_refresh_token(refresh_token)
    assert stored_session.token_hash != refresh_token
    assert stored_session.expires_at > stored_session.created_at


async def test_duplicate_email_conflicts_case_insensitively(client) -> None:
    first = await client.post(REGISTER_URL, json=VALID_BODY)
    assert first.status_code == 201

    second = await client.post(
        REGISTER_URL, json={"email": "SAM@example.com", "password": "another-pass-1"}
    )

    assert second.status_code == 409
    assert second.headers["content-type"].startswith("application/problem+json")
    body = second.json()
    assert body["code"] == "EMAIL_IN_USE"
    assert body["status"] == 409
    assert body["request_id"].startswith("req_")
    assert body["errors"] == []


async def test_invalid_payload_returns_problem_json(client) -> None:
    response = await client.post(
        REGISTER_URL, json={"email": "not-an-email", "password": "short"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["errors"]
    assert response.headers["X-Request-ID"] == body["request_id"]


async def test_server_owned_fields_cannot_be_injected(client) -> None:
    response = await client.post(
        REGISTER_URL,
        json={**VALID_BODY, "role": "ADMIN", "is_active": False},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_client_request_id_is_echoed(client) -> None:
    response = await client.post(
        REGISTER_URL, json=VALID_BODY, headers={"X-Request-ID": "req_client_supplied"}
    )

    assert response.headers["X-Request-ID"] == "req_client_supplied"
