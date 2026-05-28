"""Thread-safe holder for the speed coordinator's phase + transition
history."""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from contextlib import suppress

from asyncviz.replay.runtime.speed.models.speed_phase import (
    SpeedPhase,
    SpeedPhaseSnapshot,
)
from asyncviz.replay.runtime.speed.models.speed_request import SpeedTransition

SpeedListener = Callable[[SpeedPhaseSnapshot, SpeedPhaseSnapshot], None]


class SpeedStateHolder:
    """Atomic phase snapshot + bounded transition history."""

    __slots__ = ("_history", "_listeners", "_lock", "_state")

    def __init__(
        self,
        *,
        initial: SpeedPhaseSnapshot | None = None,
        history_capacity: int = 32,
    ) -> None:
        if history_capacity < 1:
            raise ValueError("history_capacity must be >= 1")
        self._lock = threading.RLock()
        self._state = initial or SpeedPhaseSnapshot(phase=SpeedPhase.IDLE)
        self._history: deque[SpeedTransition] = deque(maxlen=history_capacity)
        self._listeners: list[SpeedListener] = []

    @property
    def snapshot(self) -> SpeedPhaseSnapshot:
        with self._lock:
            return self._state

    @property
    def phase(self) -> SpeedPhase:
        with self._lock:
            return self._state.phase

    def transition_to(
        self, next_snapshot: SpeedPhaseSnapshot,
    ) -> SpeedPhaseSnapshot:
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

    def record_transition(self, transition: SpeedTransition) -> None:
        with self._lock:
            self._history.append(transition)

    def history(self) -> tuple[SpeedTransition, ...]:
        with self._lock:
            return tuple(self._history)

    def subscribe(self, listener: SpeedListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return _unsubscribe
