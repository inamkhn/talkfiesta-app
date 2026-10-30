"""Shared FastAPI dependencies: database session, current user, role checks."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.infrastructure.database.session import get_session
from app.modules.auth.models import User

# ``auto_error=False`` so a missing header is rendered as problem+json rather
# than Starlette's default {"detail": ...} body.
bearer_scheme = HTTPBearer(auto_error=False)

_MISSING_CREDENTIALS = "Authentication credentials were not provided."
_INVALID_TOKEN = "The access token is invalid or has expired."


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield the request-scoped session; services own commit/rollback."""

    async for session in get_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User:
    """Resolve the authenticated account from a verified access token.

    The user is always derived from the token subject, never from a body field.
    """

    if credentials is None or not credentials.credentials:
        raise UnauthorizedError(_MISSING_CREDENTIALS)

    claims = decode_access_token(credentials.credentials)
    user = await db.get(User, claims.user_id)
    if user is None:
        raise UnauthorizedError(_INVALID_TOKEN)
    if not user.is_active:
        raise ForbiddenError("This account is inactive.")
    if user.token_version != claims.token_version:
        raise UnauthorizedError(_INVALID_TOKEN)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: str):
    """Dependency factory restricting a route to the given roles."""

    async def dependency(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise ForbiddenError("Your role does not permit this action.")
        return user

    return dependency
