"""Correlation-id middleware.

Stamps every inbound request with a stable ``X-Correlation-Id`` header
(reusing the client-provided one when present, generating a uuid4 hex
otherwise). The id is exposed through a :class:`ContextVar` so logging
and downstream tracing layers can pick it up without touching the
request object.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

#: Set per-request; cleared after the response is built. Tests + ad-hoc
#: callers can read it via :func:`current_correlation_id`.
_CORRELATION_ID: ContextVar[str | None] = ContextVar("asyncviz_correlation_id", default=None)

CORRELATION_HEADER = "X-Correlation-Id"


def current_correlation_id() -> str | None:
    """Return the correlation id bound to the current request context."""
    return _CORRELATION_ID.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Read or assign a correlation id and propagate it to the response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(CORRELATION_HEADER)
        cid = incoming if incoming else uuid.uuid4().hex
        token = _CORRELATION_ID.set(cid)
        request.state.correlation_id = cid
        try:
            response = await call_next(request)
        finally:
            _CORRELATION_ID.reset(token)
        response.headers[CORRELATION_HEADER] = cid
        return response
