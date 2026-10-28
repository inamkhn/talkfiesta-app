"""Synchronous session factory for Celery workers.

Workers share the same PostgreSQL database and ORM metadata as the API but
must never share session objects across processes.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

sync_engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


def get_sync_session() -> Iterator[Session]:
    """Yield a synchronous session for worker tasks."""

    with SyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
