"""Typed reducer registry.

Replaces the old flat dict dispatch. Each reducer is a class that satisfies
the :class:`Reducer` protocol; the registry maps event classes to instances
and exposes registration / lookup / introspection.

Designed so future reducers (analytics, persistence sinks) can install
themselves at runtime without touching this module's import-time code.
"""

from __future__ import annotations

import threading

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.state.reducers.base import Reducer
from asyncviz.runtime.state.reducers.exceptions import (
    ReducerRegistrationError,
    UnknownReducerError,
)


class ReducerRegistry:
    """Class identity → :class:`Reducer` instance map.

    Thread-safe. Registration is idempotent within the same instance (registering
    the same reducer twice is a no-op) but raises :class:`ReducerRegistrationError`
    when a *different* reducer is registered for an already-claimed event class.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_event: dict[type[RuntimeEvent], Reducer] = {}

    def register(self, reducer: Reducer) -> None:
        with self._lock:
            existing = self._by_event.get(reducer.event_type)
            if existing is reducer:
                return
            if existing is not None:
                raise ReducerRegistrationError(
                    f"event class {reducer.event_type.__name__} already has reducer "
                    f"{existing.name!r}; cannot register {reducer.name!r}"
                )
            self._by_event[reducer.event_type] = reducer

    def unregister(self, event_type: type[RuntimeEvent]) -> bool:
        with self._lock:
            return self._by_event.pop(event_type, None) is not None

    def replace(self, reducer: Reducer) -> Reducer | None:
        """Force-overwrite the reducer for ``reducer.event_type``.

        Returns the previously-registered reducer if any. Use sparingly;
        the typical case is :meth:`register`.
        """
        with self._lock:
            previous = self._by_event.get(reducer.event_type)
            self._by_event[reducer.event_type] = reducer
            return previous

    def get(self, event: RuntimeEvent) -> Reducer | None:
        with self._lock:
            return self._by_event.get(type(event))

    def get_strict(self, event: RuntimeEvent) -> Reducer:
        reducer = self.get(event)
        if reducer is None:
            raise UnknownReducerError(f"no reducer registered for {type(event).__name__}")
        return reducer

    def __contains__(self, event_type: object) -> bool:
        if not isinstance(event_type, type):
            return False
        with self._lock:
            return event_type in self._by_event

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_event)

    def registered_event_types(self) -> tuple[type[RuntimeEvent], ...]:
        with self._lock:
            return tuple(self._by_event.keys())

    def describe(self) -> dict[str, str]:
        """``{event_type.__name__: reducer.name}`` mapping for debug surfaces."""
        with self._lock:
            return {cls.__name__: reducer.name for cls, reducer in self._by_event.items()}


def build_default_registry() -> ReducerRegistry:
    """Pre-populated registry with the canonical task reducers."""
    from asyncviz.runtime.state.reducers.task_cancelled import TaskCancelledReducer
    from asyncviz.runtime.state.reducers.task_completed import TaskCompletedReducer
    from asyncviz.runtime.state.reducers.task_created import TaskCreatedReducer
    from asyncviz.runtime.state.reducers.task_failed import TaskFailedReducer
    from asyncviz.runtime.state.reducers.task_resumed import TaskResumedReducer
    from asyncviz.runtime.state.reducers.task_started import TaskStartedReducer
    from asyncviz.runtime.state.reducers.task_waiting import TaskWaitingReducer

    registry = ReducerRegistry()
    registry.register(TaskCreatedReducer())
    registry.register(TaskStartedReducer())
    registry.register(TaskWaitingReducer())
    registry.register(TaskResumedReducer())
    registry.register(TaskCompletedReducer())
    registry.register(TaskCancelledReducer())
    registry.register(TaskFailedReducer())
    return registry
