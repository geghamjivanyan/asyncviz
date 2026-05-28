"""Error-normalization middleware.

Wraps unhandled exceptions raised below the routing layer into the
canonical :class:`APIErrorResponse` shape so clients see a stable JSON
envelope on every failure. Handled exceptions (``HTTPException`` etc.)
flow through unmodified — they're already structured.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from asyncviz.dashboard.exceptions import APIError, error_response_payload
from asyncviz.dashboard.middleware.correlation import current_correlation_id
from asyncviz.utils.logging import get_logger

logger = get_logger("dashboard.middleware.errors")


class ErrorNormalizationMiddleware(BaseHTTPMiddleware):
    """Catch + normalize unhandled exceptions into JSON envelopes."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except APIError as exc:
            # Typed API errors get the canonical envelope.
            payload = error_response_payload(
                code=exc.code,
                message=str(exc),
                status_code=exc.status_code,
                details=exc.details,
                correlation_id=current_correlation_id(),
            )
            backend = getattr(request.app.state, "backend", None)
            if backend is not None and getattr(backend, "metrics", None) is not None:
                backend.metrics.record_api_error(exc.code)
            return JSONResponse(payload, status_code=exc.status_code)
        except Exception as exc:
            # Truly unhandled — surface as a 500 with the canonical envelope.
            logger.exception("unhandled exception in request handler: %s", exc)
            payload = error_response_payload(
                code="internal_server_error",
                message="Internal Server Error",
                status_code=500,
                details={},
                correlation_id=current_correlation_id(),
            )
            backend = getattr(request.app.state, "backend", None)
            if backend is not None and getattr(backend, "metrics", None) is not None:
                backend.metrics.record_api_error("internal_server_error")
            return JSONResponse(payload, status_code=500)
