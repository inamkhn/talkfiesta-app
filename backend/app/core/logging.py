"""Request correlation IDs.

Clients may send ``X-Request-ID``; the server always returns its own
authoritative value, which is also what error bodies report as ``request_id``.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


def new_request_id() -> str:
    """Return a short correlation ID that is safe to log and echo."""

    return f"req_{uuid.uuid4().hex[:12]}"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to ``request.state`` and every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
