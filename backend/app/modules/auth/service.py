"""Registration use case: create the account and its first refresh session.

Both rows are written in a single transaction, so a client can never end up with
an account it cannot authenticate as, or a session pointing at no account.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    burn_password_verification,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.modules.auth.models import AuthSession, User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LoginRequest, RegisterRequest, UserSummary

logger = logging.getLogger(__name__)

DEFAULT_ROLE = "LEARNER"
EMAIL_IN_USE = "An account with this email already exists."
INVALID_CREDENTIALS = "Invalid email or password."
ACCOUNT_INACTIVE = "This account is inactive."
_EMAIL_CONFLICT = ConflictError(EMAIL_IN_USE, code="EMAIL_IN_USE")


@dataclass(frozen=True, slots=True)
class RegisteredAccount:
    """Everything the router needs to build the 201 response."""

    user: UserSummary
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime


class AuthService:
    """Application service for authentication commands."""

    def __init__(
        self, session: AsyncSession, repository: AuthRepository | None = None
    ) -> None:
        self._session = session
        self._repository = repository or AuthRepository(session)

    async def register(
        self,
        payload: RegisterRequest,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> RegisteredAccount:
        """Create an account, log it in, and return the token pair."""

        email = str(payload.email).lower()

        if await self._repository.get_user_by_email(email) is not None:
            raise ConflictError(EMAIL_IN_USE, code="EMAIL_IN_USE")

        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password(payload.password),
            display_name=payload.first_name,
            role=DEFAULT_ROLE,
        )
        self._repository.add_user(user)

        refresh_token, jti = new_refresh_token()
        session_row = AuthSession(
            user_id=user.id,
            jti=jti,
            token_hash=hash_refresh_token(refresh_token),
            family_id=uuid.uuid4(),
            user_agent=(user_agent or None) and user_agent[:255],
            ip_address=ip_address,
            expires_at=refresh_token_expiry(),
        )
        self._repository.add_session(session_row)

        try:
            await self._session.commit()
        except IntegrityError:
            # Two concurrent registrations for one address: the unique index is
            # the concurrency barrier, so surface it as the documented 409.
            await self._session.rollback()
            if await self._repository.get_user_by_email(email) is not None:
                raise _EMAIL_CONFLICT from None
            raise

        access_token, expires_in = create_access_token(
            user_id=user.id,
            role=user.role,
            token_version=user.token_version,
        )
        logger.info("user_registered user_id=%s", user.id)

        return RegisteredAccount(
            user=UserSummary(
                id=user.id,
                email=user.email,
                first_name=user.display_name,
                roles=[user.role],
                onboarding_completed=user.onboarding_completed,
            ),
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=refresh_token,
            refresh_expires_at=session_row.expires_at,
        )

    async def login(
        self,
        payload: LoginRequest,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> RegisteredAccount:
        """Verify email/password and start a new refresh-token session family."""

        user = await self._repository.get_user_by_email(str(payload.email).lower())

        # Unknown email and Google-only accounts (no password) cost the same as a
        # real verification and return the same error, so neither the response
        # nor its timing reveals whether an address is registered.
        if user is None or user.password_hash is None:
            burn_password_verification(payload.password)
            raise UnauthorizedError(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")

        if not verify_password(payload.password, user.password_hash):
            raise UnauthorizedError(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")

        # Checked only after the password is proven, so a disabled account is not
        # disclosed to someone who does not know its password.
        if not user.is_active:
            raise ForbiddenError(ACCOUNT_INACTIVE, code="ACCOUNT_INACTIVE")

        refresh_token, jti = new_refresh_token()
        session_row = AuthSession(
            user_id=user.id,
            jti=jti,
            token_hash=hash_refresh_token(refresh_token),
            family_id=uuid.uuid4(),
            user_agent=(user_agent or None) and user_agent[:255],
            ip_address=ip_address,
            expires_at=refresh_token_expiry(),
        )
        self._repository.add_session(session_row)
        await self._session.commit()

        access_token, expires_in = create_access_token(
            user_id=user.id,
            role=user.role,
            token_version=user.token_version,
        )
        logger.info("user_logged_in user_id=%s", user.id)

        return RegisteredAccount(
            user=UserSummary(
                id=user.id,
                email=user.email,
                first_name=user.display_name,
                roles=[user.role],
                onboarding_completed=user.onboarding_completed,
            ),
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=refresh_token,
            refresh_expires_at=session_row.expires_at,
        )
