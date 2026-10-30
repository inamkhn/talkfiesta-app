"""Domain exceptions mapped to ``application/problem+json`` responses.

Handlers live in :mod:`app.core.error_handlers`; services raise these and never
build HTTP responses themselves.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for errors that are safe to expose to API clients."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    title: str = "Internal Server Error"

    def __init__(
        self,
        detail: str,
        *,
        code: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code
        self.errors = errors or []
        self.headers = headers or {}


class ValidationAppError(AppError):
    """Request payload passed Pydantic but violates a domain rule."""

    status_code = 422
    code = "VALIDATION_ERROR"
    title = "Unprocessable Entity"


class UnauthorizedError(AppError):
    """Missing, malformed, expired or revoked credentials."""

    status_code = 401
    code = "UNAUTHENTICATED"
    title = "Unauthorized"


class ForbiddenError(AppError):
    """Authenticated but not allowed to perform the action."""

    status_code = 403
    code = "INSUFFICIENT_ROLE"
    title = "Forbidden"


class NotFoundError(AppError):
    """No such resource, or no such resource owned by the current user."""

    status_code = 404
    code = "RESOURCE_NOT_FOUND"
    title = "Not Found"


class ServiceUnavailableError(AppError):
    """A required external service is not configured or temporarily unavailable."""

    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    title = "Service Unavailable"


class ConflictError(AppError):
    """The request conflicts with current server state."""

    status_code = 409
    code = "CONFLICT"
    title = "Conflict"


class RateLimitedError(AppError):
    """Too many requests; ``headers`` carries ``Retry-After``."""

    status_code = 429
    code = "RATE_LIMITED"
    title = "Too Many Requests"

    def __init__(
        self, detail: str, *, retry_after: int, code: str | None = None
    ) -> None:
        super().__init__(
            detail, code=code, headers={"Retry-After": str(max(retry_after, 1))}
        )
