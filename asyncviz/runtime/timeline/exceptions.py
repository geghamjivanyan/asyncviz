from __future__ import annotations


class TimelineError(Exception):
    """Base class for every :class:`TimelineSegmentEngine` failure."""


class InvalidSegmentTransitionError(TimelineError):
    """Raised when a transition would corrupt an active span.

    Examples: closing a segment that was never opened, opening a Run
    segment while one is already active. The engine surfaces these via
    metrics; the strict variant is intended for tests / replay tools.
    """


class SegmentReconstructionError(TimelineError):
    """Raised when :meth:`TimelineSegmentEngine.rebuild` finds inconsistent input."""


class SegmentBufferOverflowError(TimelineError):
    """Reserved — raised by the bounded-buffer strategies once they land."""
