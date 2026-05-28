from __future__ import annotations


class StateStoreError(Exception):
    """Base class for every :class:`RuntimeStateStore` failure."""


class StaleEventError(StateStoreError):
    """Raised when an event arrives with a sequence ``<=`` the store's high-water mark.

    The default ``apply()`` path *suppresses* stale events silently (counts
    them in metrics). This exception is only raised by the strict variant
    used by tests and replay tools.
    """


class UnknownProjectionError(StateStoreError):
    """Raised when a caller asks for a projection name that isn't registered."""


class StateRebuildError(StateStoreError):
    """Raised when :meth:`RuntimeStateStore.rebuild` encounters a corrupted event stream."""
