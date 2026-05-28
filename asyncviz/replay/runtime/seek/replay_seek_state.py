"""Thread-safe holder for the seek coordinator's state.

Owns one :class:`SeekStateSnapshot` behind a lock; notifies
listeners on every transition. Listener exceptions are isolated so
a buggy subscriber can't deadlock the coordinator.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import suppress

from asyncviz.replay.runtime.seek.models.seek_state import (
    SeekState,
    SeekStateSnapshot,
)

SeekStateListener = Callable[[SeekStateSnapshot, SeekStateSnapshot], None]


class SeekStateHolder:
    """Holds the coordinator's snapshot + fans transitions out."""

    __slots__ = ("_listeners", "_lock", "_state")

    def __init__(self, initial: SeekStateSnapshot | None = None) -> None:
        self._lock = threading.RLock()
        self._state = initial or SeekStateSnapshot(state=SeekState.IDLE)
        self._listeners: list[SeekStateListener] = []

    @property
    def snapshot(self) -> SeekStateSnapshot:
        with self._lock:
            return self._state

    @property
    def state(self) -> SeekState:
        with self._lock:
            return self._state.state

    def transition_to(self, next_snapshot: SeekStateSnapshot) -> SeekStateSnapshot:
        with self._lock:
            previous = self._state
            if previous == next_snapshot:
                return previous
            self._state = next_snapshot
            listeners = tuple(self._listeners)
        for listener in listeners:
            with suppress(Exception):
                listener(previous, next_snapshot)
        return next_snapshot

    def subscribe(self, listener: SeekStateListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return _unsubscribe
