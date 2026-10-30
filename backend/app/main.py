"""FastAPI application factory and local entry point."""

from __future__ import annotations

import asyncio
import sys

import uvicorn
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import RequestContextMiddleware

# psycopg's async driver cannot run on Windows' default ProactorEventLoop, and
# the policy must be installed before the loop exists. Prefer
# ``uv run python -m app.main``; bare ``uvicorn app.main:app`` creates the loop
# before this module is imported, so the policy would arrive too late.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def create_app() -> FastAPI:
    """Build the ASGI application."""

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["Ops"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
