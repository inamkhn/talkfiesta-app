"""Persistence for accounts and refresh sessions.

Repositories translate intent into SQLAlchemy statements; they never commit or
roll back, because the application service owns the transaction boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AuthSession, User


class AuthRepository:
    """Query object bound to one request-scoped session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_email(
        self, email: str, *, for_update: bool = False
    ) -> User | None:
        """Case-insensitive lookup that uses ``ix_users_email_lower``."""

        statement = select(User).where(func.lower(User.email) == email.lower())
        if for_update:
            statement = statement.with_for_update().execution_options(
                populate_existing=True
            )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def lock_user(self, user_id: uuid.UUID) -> User | None:
        return await self._session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    async def get_user_by_google_subject(self, subject: str) -> User | None:
        return await self._session.scalar(
            select(User).where(User.google_sub == subject).with_for_update()
        )

    async def revoke_user_sessions(self, user_id: uuid.UUID, now: datetime) -> None:
        await self._session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason="PASSWORD_RESET")
        )

    def add_user(self, user: User) -> None:
        self._session.add(user)

    def add_session(self, session_row: AuthSession) -> None:
        self._session.add(session_row)

    async def get_session_by_token_hash(self, token_hash: str) -> AuthSession | None:
        statement = select(AuthSession).where(AuthSession.token_hash == token_hash)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def lock_refresh_owner(self, token_hash: str) -> User | None:
        """Serialize rotation and reuse detection across all of an owner's tokens."""
        owner_id = (
            select(AuthSession.user_id)
            .where(AuthSession.token_hash == token_hash)
            .scalar_subquery()
        )
        result = await self._session.execute(
            select(User).where(User.id == owner_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        await self._session.execute(
            update(AuthSession)
            .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason="REUSE_DETECTED")
        )
