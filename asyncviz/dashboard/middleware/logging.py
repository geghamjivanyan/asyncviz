"""Structured request-logging middleware.

Emits one log line per request at DEBUG. Production deployments override
the log level via the standard ``logging`` config; tests stay quiet by
default. Lines are formatted for ingestion by line-oriented log shippers
(method, path, status, duration, correlation id).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from asyncviz.dashboard.middleware.correlation import current_correlation_id
from asyncviz.utils.logging import get_logger

logger = get_logger("dashboard.middleware.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit one structured log line per request.

    Sits after the timing middleware so it can pick up
    ``request.state.response_time_ms``. Skips static-asset paths to keep
    the log volume sane.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if _should_log(request):
            duration_ms = getattr(request.state, "response_time_ms", None)
            duration_repr = f"{duration_ms:.3f}ms" if duration_ms is not None else "?"
            logger.debug(
                "%s %s %d cid=%s in %s",
                request.method,
                request.url.path,
                response.status_code,
                current_correlation_id() or "-",
                duration_repr,
            )
        return response


def _should_log(request: Request) -> bool:
    path = request.url.path
    if path.startswith("/assets/"):
        return False
    return path not in ("/favicon.ico", "/robots.txt")
