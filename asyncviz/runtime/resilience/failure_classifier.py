"""Map exceptions to :class:`FailureKind` buckets.

Subsystem code calls :func:`classify_exception` to convert a raised
exception into the coarse bucket the manager understands. The
function is pure + side-effect-free; identical inputs always
produce identical outputs.

The classifier accepts an optional **payload kind** string (e.g.
``"replay-frame"``, ``"reducer-projection"``) that callers attach
when they know which kind of payload caused the failure — the
manager uses it for quarantine decisions.
"""

from __future__ import annotations

import asyncio

from asyncviz.runtime.resilience.models.failure_kind import FailureKind

_CORRUPTION_HINTS: tuple[str, ...] = (
    "corrupted",
    "corruption",
    "checksum",
    "decode-failed",
    "deserialize",
    "schema",
    "integrity",
)

_PROTOCOL_HINTS: tuple[str, ...] = (
    "handshake",
    "protocol",
    "websocket",
    "frame-too-large",
)

_RESOURCE_HINTS: tuple[str, ...] = (
    "memory",
    "disk",
    "no-space",
    "queue-full",
    "semaphore",
    "exhaust",
)


def classify_exception(exc: BaseException) -> FailureKind:
    """Return the canonical bucket for ``exc``."""
    if isinstance(exc, asyncio.CancelledError):
        return FailureKind.CANCELLED
    if isinstance(exc, (AssertionError, TypeError, AttributeError, NameError, SyntaxError)):
        return FailureKind.PROGRAMMER
    if isinstance(exc, MemoryError):
        return FailureKind.RESOURCE
    if isinstance(exc, (TimeoutError,)):
        return FailureKind.TRANSIENT
    if isinstance(exc, (OSError, BrokenPipeError, ConnectionError)):
        # Distinguish disk-full (errno=ENOSPC) from regular IO.
        errno = getattr(exc, "errno", None)
        if errno in (28,):  # ENOSPC
            return FailureKind.RESOURCE
        return FailureKind.TRANSIENT
    message = _normalize_message(exc)
    if any(hint in message for hint in _CORRUPTION_HINTS):
        return FailureKind.CORRUPTION
    if any(hint in message for hint in _PROTOCOL_HINTS):
        return FailureKind.PROTOCOL
    if any(hint in message for hint in _RESOURCE_HINTS):
        return FailureKind.RESOURCE
    return FailureKind.UNKNOWN


def classify_marker(marker: str) -> FailureKind:
    """Classify a non-exception failure flag (e.g. emitted by the
    replay decoder when it observes a corrupted frame). Marker
    strings are lowercase + dash-separated."""
    if marker in {"cancelled", "cancellation"}:
        return FailureKind.CANCELLED
    if any(hint in marker for hint in _CORRUPTION_HINTS):
        return FailureKind.CORRUPTION
    if any(hint in marker for hint in _PROTOCOL_HINTS):
        return FailureKind.PROTOCOL
    if any(hint in marker for hint in _RESOURCE_HINTS):
        return FailureKind.RESOURCE
    if marker.endswith("-timeout") or marker == "timeout":
        return FailureKind.TRANSIENT
    if marker.startswith("assert") or marker == "programmer-error":
        return FailureKind.PROGRAMMER
    return FailureKind.UNKNOWN


def _normalize_message(exc: BaseException) -> str:
    detail = (str(exc) or exc.__class__.__name__).lower()
    return detail[:200]
