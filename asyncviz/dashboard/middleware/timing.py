"""Request-timing middleware.

Measures wall-clock duration of each request via :func:`time.perf_counter`
and stamps the response with an ``X-Response-Time-Ms`` header. Pushes the
per-request reading into :class:`BackendMetrics` so the dashboard can
expose backend latency without external observability infrastructure.

Static-asset paths are excluded from the metrics tally to keep the
counters focused on API + websocket traffic.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from asyncviz.dashboard.state.backend_metrics import BackendMetrics

TIMING_HEADER = "X-Response-Time-Ms"


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Time each request, stamp the response header, feed :class:`BackendMetrics`."""

    def __init__(self, app, *, metrics: BackendMetrics | None = None) -> None:
        super().__init__(app)
        self._metrics = metrics

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            request.state.response_time_ms = elapsed_ms
            metrics = _resolve_metrics(self._metrics, request)
            if metrics is not None and _should_count(request):
                metrics.record_request(
                    method=request.method,
                    path=request.url.path,
                    status_code=status,
                    duration_ms=elapsed_ms,
                )
            # Stamp the header on the response we got back. If the response
            # has already been sent (rare; e.g. streaming), this is a no-op.
            if "response" in locals():
                response.headers.setdefault(TIMING_HEADER, f"{elapsed_ms:.3f}")


def _resolve_metrics(
    static: BackendMetrics | None,
    request: Request,
) -> BackendMetrics | None:
    if static is not None:
        return static
    backend = getattr(request.app.state, "backend", None)
    if backend is None:
        return None
    return getattr(backend, "metrics", None)


def _should_count(request: Request) -> bool:
    """Skip per-request counters for static-asset paths to keep counters meaningful."""
    path = request.url.path
    if path.startswith("/assets/"):
        return False
    return path not in ("/favicon.ico", "/robots.txt")
