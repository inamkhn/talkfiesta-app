"""API contract tests for ``POST /api/v1/auth/login``."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import decode_access_token, hash_refresh_token
from app.modules.auth.models import AuthSession, User

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CREDENTIALS = {"email": "sam@example.com", "password": "supersecret123"}


async def test_login_issues_tokens_and_new_session(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post(REGISTER_URL, json=CREDENTIALS)
    client.cookies.clear()

    response = await client.post(
        LOGIN_URL, json={"email": "  SAM@Example.com ", "password": CREDENTIALS["password"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["user"]["email"] == "sam@example.com"
    assert str(decode_access_token(body["access_token"]).user_id) == body["user"]["id"]

    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Path=/api/v1/auth" in response.headers["set-cookie"]
    refresh_token = response.cookies.get("tf_refresh")
    assert refresh_token

    async with session_factory() as session:
        rows = (await session.execute(select(AuthSession))).scalars().all()

    # One session from register, one new family from login; only the hash is stored.
    assert len(rows) == 2
    assert len({row.family_id for row in rows}) == 2
    assert hash_refresh_token(refresh_token) in {row.token_hash for row in rows}


async def test_wrong_password_and_unknown_email_look_identical(client) -> None:
    await client.post(REGISTER_URL, json=CREDENTIALS)

    wrong_password = await client.post(
        LOGIN_URL, json={"email": CREDENTIALS["email"], "password": "not-the-password"}
    )
    unknown_email = await client.post(
        LOGIN_URL, json={"email": "nobody@example.com", "password": "not-the-password"}
    )

    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == "INVALID_CREDENTIALS"
        assert "tf_refresh" not in response.cookies
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


async def test_account_without_password_cannot_log_in(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post(REGISTER_URL, json=CREDENTIALS)
    async with session_factory() as session:
        await session.execute(update(User).values(password_hash=None))
        await session.commit()

    response = await client.post(LOGIN_URL, json=CREDENTIALS)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


async def test_inactive_account_is_forbidden_only_with_correct_password(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await client.post(REGISTER_URL, json=CREDENTIALS)
    async with session_factory() as session:
        await session.execute(update(User).values(is_active=False))
        await session.commit()

    correct = await client.post(LOGIN_URL, json=CREDENTIALS)
    wrong = await client.post(
        LOGIN_URL, json={"email": CREDENTIALS["email"], "password": "not-the-password"}
    )

    assert correct.status_code == 403
    assert correct.json()["code"] == "ACCOUNT_INACTIVE"
    assert wrong.status_code == 401


async def test_login_rejects_invalid_payload(client) -> None:
    response = await client.post(
        LOGIN_URL, json={"email": "sam@example.com", "password": "x", "role": "ADMIN"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"

