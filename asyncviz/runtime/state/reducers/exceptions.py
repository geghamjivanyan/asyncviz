from __future__ import annotations


class ReducerError(Exception):
    """Base class for every reducer-layer failure."""


class InvalidTransitionError(ReducerError):
    """Raised by the validation layer when a transition isn't allowed.

    The store catches this and converts it into an ``events_rejected``
    metric — reducers themselves don't propagate it past their own
    boundary, but it's exposed here so tests can assert against the type.
    """


class TerminalStateLockedError(ReducerError):
    """Raised when a non-terminal event targets a task already in a terminal state.

    A specific subclass of :class:`InvalidTransitionError`-style rejection
    that captures one of the most common replay patterns: late events
    arriving for an already-completed task. Surfaced separately so the
    metrics layer can break it out from generic invalid transitions.
    """


class UnknownReducerError(ReducerError):
    """Raised on dispatch when no reducer is registered for an event class."""


class ReducerRegistrationError(ReducerError):
    """Raised on duplicate or invalid :meth:`ReducerRegistry.register` calls."""
