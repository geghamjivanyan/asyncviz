"""Coarse failure-kind enumeration.

The classifier maps every observed exception (or non-exception
failure marker) to one of these buckets. The manager + supervisor
read the bucket to decide how to react — *not* the original
exception class, so a future ``ReplayCorruptionError`` and an
existing :class:`ValueError` with a ``"corrupted-frame"`` marker
both land on :attr:`CORRUPTION`.
"""

from __future__ import annotations

from enum import StrEnum


class FailureKind(StrEnum):
    TRANSIENT = "transient"
    """Network blips, timeouts, retryable errors."""

    CORRUPTION = "corruption"
    """Data integrity violations — quarantine the payload, do not
    retry blindly."""

    PROTOCOL = "protocol"
    """The peer broke the wire contract (e.g. websocket handshake)."""

    RESOURCE = "resource"
    """Out-of-memory, disk-full, semaphore exhausted."""

    CANCELLED = "cancelled"
    """asyncio cancellation. Usually structural, not a failure."""

    PROGRAMMER = "programmer"
    """AssertionError / TypeError — a bug; don't auto-recover."""

    UNKNOWN = "unknown"


CORRUPTION_KINDS: frozenset[FailureKind] = frozenset({FailureKind.CORRUPTION})
DO_NOT_RETRY: frozenset[FailureKind] = frozenset(
    {FailureKind.PROGRAMMER, FailureKind.CORRUPTION},
)
