"""HTTP layer for ``/auth``.

Routers translate HTTP into service calls and back; they hold no business rules
and never touch the database directly.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.deps import DbSession
from app.core.config import settings
from app.infrastructure.cache.redis import enforce_rate_limit
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])

_CREATED_USER_LOCATION = "/api/v1/users/me"


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterResponse,
    summary="Create an account and start its first session",
    responses={
        409: {"description": "EMAIL_IN_USE: the address is already registered"},
        422: {"description": "VALIDATION_ERROR: malformed request body"},
        429: {"description": "RATE_LIMITED: too many registrations from this IP"},
    },
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> RegisterResponse:
    """Register with email and password.

    Issues the access token in the body and the refresh token as an HttpOnly
    cookie scoped to ``/api/v1/auth`` so it is only ever sent to the endpoints
    that rotate or revoke it.
    """

    client_ip = request.client.host if request.client else "unknown"
    await enforce_rate_limit(
        f"ratelimit:register:ip:{client_ip}",
        limit=settings.register_rate_limit_per_ip_per_hour,
        window_seconds=3600,
    )

    account = await AuthService(db).register(
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip,
    )

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=account.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86_400,
        path=settings.refresh_cookie_path,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
    )
    response.headers["Location"] = _CREATED_USER_LOCATION

    return RegisterResponse(
        access_token=account.access_token,
        expires_in=account.expires_in,
        user=account.user,
    )


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=LoginResponse,
    summary="Authenticate with email and password",
    responses={
        401: {"description": "INVALID_CREDENTIALS: wrong email or password"},
        403: {"description": "ACCOUNT_INACTIVE: the account is disabled"},
        422: {"description": "VALIDATION_ERROR: malformed request body"},
        429: {"description": "RATE_LIMITED: too many login attempts from this IP"},
    },
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> LoginResponse:
    """Log in with email and password.

    Issues the access token in the body and a fresh refresh token as an HttpOnly
    cookie, exactly like ``/register``.
    """

    client_ip = request.client.host if request.client else "unknown"
    await enforce_rate_limit(
        f"ratelimit:login:ip:{client_ip}",
        limit=settings.login_rate_limit_per_ip_per_hour,
        window_seconds=3600,
    )

    account = await AuthService(db).login(
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip,
    )

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=account.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86_400,
        path=settings.refresh_cookie_path,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="lax",
    )

    return LoginResponse(
        access_token=account.access_token,
        expires_in=account.expires_in,
        user=account.user,
    )
