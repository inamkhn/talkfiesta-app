"""Persistence for accounts and refresh sessions.

Repositories translate intent into SQLAlchemy statements; they never commit or
roll back, because the application service owns the transaction boundary.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AuthSession, User


class AuthRepository:
    """Query object bound to one request-scoped session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_email(self, email: str) -> User | None:
        """Case-insensitive lookup that uses ``ix_users_email_lower``."""

        statement = select(User).where(func.lower(User.email) == email.lower())
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    def add_user(self, user: User) -> None:
        self._session.add(user)

    def add_session(self, session_row: AuthSession) -> None:
        self._session.add(session_row)

    async def get_session_by_token_hash(self, token_hash: str) -> AuthSession | None:
        statement = select(AuthSession).where(AuthSession.token_hash == token_hash)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
