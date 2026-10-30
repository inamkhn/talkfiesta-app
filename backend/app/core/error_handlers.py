"""Map domain and framework exceptions to ``application/problem+json``."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

PROBLEM_TYPE_BASE = "https://api.talkfiesta.example/problems"

_HTTP_STATUS_CODES = {
    401: "UNAUTHENTICATED",
    403: "INSUFFICIENT_ROLE",
    404: "RESOURCE_NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def _problem(
    request: Request,
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {
        "type": f"{PROBLEM_TYPE_BASE}/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status,
        "code": code,
        "detail": detail,
        "request_id": _request_id(request),
        "errors": errors or [],
    }
    return JSONResponse(
        body,
        status_code=status,
        media_type="application/problem+json",
        headers=headers,
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Render a deliberately exposed domain error."""

    return _problem(
        request,
        status=exc.status_code,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        errors=exc.errors,
        headers=exc.headers,
    )


async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Give framework-raised ``HTTPException`` the same body shape."""

    code = _HTTP_STATUS_CODES.get(exc.status_code, "HTTP_ERROR")
    return _problem(
        request,
        status=exc.status_code,
        code=code,
        title=str(exc.detail) if exc.detail else "Error",
        detail=str(exc.detail) if exc.detail else "The request could not be served.",
        headers=dict(exc.headers or {}),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Collapse Pydantic errors into ``422 VALIDATION_ERROR``."""

    errors = [
        {
            "loc": [str(part) for part in error.get("loc", ())],
            "msg": str(error.get("msg", "Invalid value.")),
            "type": str(error.get("type", "value_error")),
        }
        for error in exc.errors()
    ]
    return _problem(
        request,
        status=422,
        code="VALIDATION_ERROR",
        title="Unprocessable Entity",
        detail="The request body failed validation.",
        errors=errors,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last resort: log with the correlation ID, never leak internals."""

    logger.exception("unhandled_error request_id=%s", _request_id(request))
    return _problem(
        request,
        status=500,
        code="INTERNAL_ERROR",
        title="Internal Server Error",
        detail="An unexpected error occurred. Quote the request_id when reporting it.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach every handler needed for the problem+json contract."""

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
