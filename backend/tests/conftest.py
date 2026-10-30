"""Shared fixtures for the backend test suite.

API tests use a real PostgreSQL database when ``TEST_DATABASE_URL`` is set and
fall back to in-memory SQLite so the suite still runs where Docker is
unavailable. The SQLite fallback proves wiring and behaviour only; Postgres-only
semantics (partial unique indexes, ``JSONB``, real concurrency) need the
integration suite.
"""

from __future__ import annotations

import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("REFRESH_COOKIE_SECURE", "false")

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import JSONB as PostgresJSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool, StaticPool

from app.api.deps import get_db
from app.infrastructure.database import model_registry  # noqa: F401
from app.infrastructure.database.base import Base
from app.main import app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite://")


@compiles(PostgresUUID, "sqlite")
def _compile_postgres_uuid_for_sqlite(type_, compiler, **kw) -> str:
    """Render the models' ``postgresql.UUID`` columns on the SQLite fallback."""

    return "CHAR(32)"


@compiles(PostgresJSONB, "sqlite")
def _compile_postgres_jsonb_for_sqlite(type_, compiler, **kw) -> str:
    """Render the models' ``postgresql.JSONB`` columns on the SQLite fallback."""

    return "JSON"


def _engine_options() -> dict[str, object]:
    if TEST_DATABASE_URL.startswith("sqlite"):
        # A single shared connection keeps the in-memory database alive.
        return {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    return {"poolclass": NullPool}


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Give each test an empty schema and a session factory bound to it."""

    engine = create_async_engine(TEST_DATABASE_URL, **_engine_options())
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """HTTP client wired to the real app with the test database injected."""

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
