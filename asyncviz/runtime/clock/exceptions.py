from __future__ import annotations


class ClockError(Exception):
    """Base class for all RuntimeClock failures."""


class ClockSequenceOverflowError(ClockError):
    """Raised when the sequence counter would overflow its declared bound.

    The default bound is huge (``2**63 - 1``), so in practice this is
    defensive — it exists so a runaway producer surfaces as a typed error
    rather than silently wrapping to a smaller value.
    """


class ClockSkewError(ClockError):
    """Reserved for future distributed-clock synchronization failures.

    Held in the API surface so callers can `except ClockSkewError` today and
    still benefit when the synchronization module lands.
    """
