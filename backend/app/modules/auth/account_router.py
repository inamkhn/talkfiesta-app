"""Password recovery, email verification, and Google ID-token exchange."""

import asyncio

from fastapi import APIRouter, BackgroundTasks, Request, Response, status

from app.api.deps import DbSession
from app.core.config import settings
from app.core.security import hash_refresh_token
from app.infrastructure.cache.redis import enforce_rate_limit
from app.infrastructure.email import require_email_configuration
from app.infrastructure.google_identity import verify_google_token
from app.modules.auth.recovery import RecoveryService, deliver_account_email
from app.modules.auth.schemas import (
    ActionTokenRequest,
    EmailActionRequest,
    GoogleExchangeRequest,
    LoginResponse,
    MessageResponse,
    ResetPasswordRequest,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


async def throttle(request: Request, action: str, email: str | None = None) -> None:
    ip = request.client.host if request.client else "unknown"
    await enforce_rate_limit(
        f"ratelimit:{action}:ip:{ip}",
        limit=settings.auth_action_rate_limit_per_ip_per_hour,
        window_seconds=3600,
    )
    if email is not None:
        await enforce_rate_limit(
            f"ratelimit:{action}:email:{hash_refresh_token(email)}",
            limit=3,
            window_seconds=3600,
        )


@router.post("/forgot-password", response_model=MessageResponse, status_code=202)
async def forgot_password(
    payload: EmailActionRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
) -> MessageResponse:
    email = str(payload.email).lower()
    await throttle(request, "forgot-password", email)
    require_email_configuration()
    background_tasks.add_task(deliver_account_email, email, "password_reset")
    response.headers["Cache-Control"] = "no-store"
    return MessageResponse(
        message="If this account is eligible, a password reset link will be sent."
    )


@router.post(
    "/reset-password", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def reset_password(
    payload: ResetPasswordRequest, request: Request, db: DbSession
) -> Response:
    await throttle(request, "reset-password")
    await RecoveryService(db).reset_password(payload.token, payload.new_password)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


@router.post(
    "/request-email-verification", response_model=MessageResponse, status_code=202
)
async def request_email_verification(
    payload: EmailActionRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
) -> MessageResponse:
    email = str(payload.email).lower()
    await throttle(request, "email-verification", email)
    require_email_configuration()
    background_tasks.add_task(deliver_account_email, email, "email_verification")
    response.headers["Cache-Control"] = "no-store"
    return MessageResponse(
        message="If this account is eligible, a verification link will be sent."
    )


@router.post(
    "/verify-email", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def verify_email(
    payload: ActionTokenRequest, request: Request, db: DbSession
) -> Response:
    await throttle(request, "verify-email")
    await RecoveryService(db).verify_email(payload.token)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.post("/google/exchange", response_model=LoginResponse)
async def google_exchange(
    payload: GoogleExchangeRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> LoginResponse:
    """Exchange the Google Identity Services credential (ID token), not an auth code."""
    await throttle(request, "google-exchange")
    identity = await asyncio.to_thread(verify_google_token, payload.id_token)
    account = await AuthService(db).google_exchange(
        identity,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        account.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86_400,
        path=settings.refresh_cookie_path,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return LoginResponse(
        access_token=account.access_token,
        expires_in=account.expires_in,
        user=account.user,
    )
