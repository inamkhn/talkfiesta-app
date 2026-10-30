"""Email actions with state-bound tokens and atomic single-use consumption."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.action_tokens import (
    ActionPurpose,
    create_action_token,
    decode_action_token,
    invalid_action_token,
)
from app.core.security import hash_password
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.email import send_action_email
from app.modules.auth.models import User
from app.modules.auth.repository import AuthRepository

logger = logging.getLogger(__name__)


async def deliver_account_email(email: str, purpose: ActionPurpose) -> None:
    """Run after the generic response, using an independent database session.

    Lookup and SMTP timing do not disclose whether an account exists. This is
    best-effort in-process delivery; users can request another link on failure.
    """
    try:
        async with AsyncSessionLocal() as db:
            user = await AuthRepository(db).get_user_by_email(email)
            if user is None or not user.is_active:
                return
            if purpose == "password_reset" and user.password_hash is None:
                return
            if purpose == "email_verification" and user.email_verified_at is not None:
                return
            token = create_action_token(user, purpose)
            recipient = user.email
        await asyncio.to_thread(
            send_action_email,
            recipient,
            token,
            reset_password=purpose == "password_reset",
        )
    except Exception as exc:
        # Do not log SMTP exception text: it can contain recipient details.
        logger.error(
            "account_email_failed purpose=%s error_type=%s", purpose, type(exc).__name__
        )


class RecoveryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = AuthRepository(session)

    async def _resolve(self, token: str, purpose: ActionPurpose) -> User:
        claims = decode_action_token(token, purpose)
        user = await self._repository.lock_user(uuid.UUID(claims["sub"]))
        if (
            user is None
            or not user.is_active
            or user.email != claims["email"]
            or user.token_version != claims["tv"]
        ):
            raise invalid_action_token()
        return user

    async def reset_password(self, token: str, password: str) -> None:
        user = await self._resolve(token, "password_reset")
        if user.password_hash is None:
            raise invalid_action_token()
        user.password_hash = await asyncio.to_thread(hash_password, password)
        user.token_version += 1
        await self._repository.revoke_user_sessions(user.id, datetime.now(UTC))
        # Password, access-token invalidation, and refresh revocation commit together.
        await self._session.commit()

    async def verify_email(self, token: str) -> None:
        user = await self._resolve(token, "email_verification")
        if user.email_verified_at is not None:
            raise invalid_action_token()
        user.email_verified_at = datetime.now(UTC)
        await self._session.commit()
