from __future__ import annotations


class StreamingError(Exception):
    """Base class for every :class:`RuntimeStreamingEngine` failure."""


class StreamNotRunningError(StreamingError):
    """Raised when an operation needs the streaming engine to be started."""


class DuplicateSourceError(StreamingError):
    """Raised when the same source is bound twice."""
