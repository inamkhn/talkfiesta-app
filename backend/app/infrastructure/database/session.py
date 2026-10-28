"""Async session factory for the FastAPI process.

The async psycopg driver needs a selector event loop. On Windows the default
ProactorEventLoop fails on connect with ``psycopg.InterfaceError``, so the
application entry point must install ``asyncio.WindowsSelectorEventLoopPolicy``
before creating the engine (Linux/Docker containers are unaffected).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async session, rolling back on failure."""

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
