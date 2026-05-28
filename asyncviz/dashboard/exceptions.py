"""Typed API error hierarchy + canonical response envelope.

The dashboard's REST + WS handlers raise :class:`APIError` subclasses; the
:class:`ErrorNormalizationMiddleware` (or an equivalent FastAPI exception
handler) renders them as a stable JSON envelope::

    {
      "error": {
        "code": "<machine-name>",
        "message": "<human-readable>",
        "details": {...},
        "correlation_id": "<hex>",
        "status_code": 4xx | 5xx
      }
    }

This shape is part of the public protocol — coordinate with the
TypeScript ``APIErrorResponse`` definition before changing fields.
"""

from __future__ import annotations

from typing import Any, ClassVar


class APIError(Exception):
    """Base class for typed API failures.

    Subclasses set :attr:`code` (stable machine name), :attr:`status_code`
    (HTTP status), and optionally :attr:`default_details` (a static dict
    merged with per-raise ``details``). The middleware does the rendering;
    handlers just ``raise``.
    """

    code: ClassVar[str] = "api_error"
    status_code: ClassVar[int] = 500
    default_details: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.code)
        merged: dict[str, Any] = {}
        merged.update(self.default_details)
        if details:
            merged.update(details)
        self.details = merged


class NotFoundError(APIError):
    code = "not_found"
    status_code = 404


class ConflictError(APIError):
    code = "conflict"
    status_code = 409


class ValidationError(APIError):
    code = "validation_error"
    status_code = 422


class UnavailableError(APIError):
    code = "service_unavailable"
    status_code = 503


class ReplayWindowMissError(APIError):
    """Replay was requested but retention has rolled past the asked sequence."""

    code = "replay_window_miss"
    status_code = 409


class WebSocketProtocolError(APIError):
    """Raised by WS handshake checks that the protocol layer can't accept."""

    code = "websocket_protocol_error"
    status_code = 400


def error_response_payload(
    *,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None,
    correlation_id: str | None,
) -> dict[str, Any]:
    """Build the canonical JSON envelope.

    Kept here (and not on :class:`APIError`) so other places —
    notably the in-app ``HTTPException`` adapter and FastAPI's built-in
    validation errors — can produce the same shape without subclassing.
    """
    return {
        "error": {
            "code": code,
            "message": message,
            "details": dict(details) if details else {},
            "correlation_id": correlation_id,
            "status_code": status_code,
        }
    }


__all__ = [
    "APIError",
    "ConflictError",
    "NotFoundError",
    "ReplayWindowMissError",
    "UnavailableError",
    "ValidationError",
    "WebSocketProtocolError",
    "error_response_payload",
]
