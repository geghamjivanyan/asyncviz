from __future__ import annotations


class EventBusError(Exception):
    """Base class for every event-bus failure."""


class EventBusNotRunningError(EventBusError):
    """Raised when an operation requires a running bus and the bus is stopped."""


class InvalidSubscriptionError(EventBusError):
    """Raised when ``subscribe`` is called with an unusable callback or filter."""
