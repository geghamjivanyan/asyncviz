"""Reducer-subsystem failure isolation adapter.

Reducers are pure functions over event streams; a reducer that
raises corrupts the projection it owns. The adapter wraps each
reducer call in a boundary and tracks per-reducer fault counts so
the manager can disable a misbehaving reducer instead of letting
it poison every projection.
"""

from __future__ import annotations

import threading

from asyncviz.runtime.resilience.failure_domain import FailureDomain
from asyncviz.runtime.resilience.subsystem_boundary import SubsystemBoundary


class ReducerFailureIsolation:
    __slots__ = ("_disabled", "_domain", "_lock")

    def __init__(self, domain: FailureDomain) -> None:
        self._domain = domain
        self._lock = threading.Lock()
        self._disabled: set[str] = set()

    def isolate_apply(
        self,
        *,
        reducer_id: str,
        suppress: bool = True,
    ) -> SubsystemBoundary:
        return SubsystemBoundary(
            self._domain,
            payload_kind=reducer_id,
            suppress=suppress,
            on_failure=lambda event: self._note_disabled(event.payload_kind, event.recoverable),
            swallow_unavailable=True,
        )

    def disabled_reducers(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._disabled))

    def is_disabled(self, reducer_id: str) -> bool:
        with self._lock:
            return reducer_id in self._disabled

    def reinstate(self, reducer_id: str) -> bool:
        with self._lock:
            existed = reducer_id in self._disabled
            self._disabled.discard(reducer_id)
        if existed:
            self._domain.release_quarantine(reducer_id)
        return existed

    def _note_disabled(self, reducer_id: str, recoverable: bool) -> None:
        if not reducer_id or recoverable:
            return
        with self._lock:
            self._disabled.add(reducer_id)
