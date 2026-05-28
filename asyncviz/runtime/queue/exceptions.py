from __future__ import annotations


class EventQueueError(Exception):
    """Base class for every :class:`InternalEventQueue` failure."""


class EventQueueNotRunningError(EventQueueError):
    """Raised when an operation requires the queue to be in the running state.

    Construction and configuration are always legal; ``publish`` / ``drain``
    / ``join`` require ``start()`` to have been called first.
    """


class EventQueueOverflowError(EventQueueError):
    """Raised by the ``FAIL_FAST`` overflow strategy when capacity is exceeded.

    The ``DROP_OLDEST`` and ``DROP_NEWEST`` strategies never raise this — they
    silently discard and record the drop in metrics. Only ``FAIL_FAST``
    propagates back to the publisher.
    """


class RetentionConfigError(EventQueueError):
    """Raised when retention parameters are inconsistent (e.g. negative size)."""
