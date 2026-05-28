"""Playback speed controller.

A thin wrapper around the clock's ``set_speed`` that adds:

* clamping to a sane range (``MIN_SPEED`` .. ``MAX_SPEED``)
* listener hooks so consumers (UI, metrics) can react to changes
* a history ring so diagnostics can show recent speed transitions
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from asyncviz.replay.runtime.replay_clock import ReplayClock

MIN_SPEED: Final[float] = 0.05
MAX_SPEED: Final[float] = 32.0


SpeedChangeListener = Callable[[float, float], None]
"""``listener(old_speed, new_speed)``. Called synchronously after the
clock has been updated."""


@dataclass(frozen=True, slots=True)
class SpeedChange:
    """One historical speed transition."""

    old_speed: float
    new_speed: float
    at_virtual_ns: int


class SpeedController:
    """Owns playback-speed changes + listener fan-out."""

    __slots__ = ("_clock", "_history", "_listeners", "_lock")

    def __init__(self, clock: ReplayClock, *, history_capacity: int = 16) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._listeners: list[SpeedChangeListener] = []
        self._history: deque[SpeedChange] = deque(maxlen=history_capacity)

    @property
    def current(self) -> float:
        return self._clock.speed

    def set(self, speed: float) -> float:
        clamped = max(MIN_SPEED, min(MAX_SPEED, float(speed)))
        with self._lock:
            old = self._clock.speed
            if old == clamped:
                return clamped
            self._clock.set_speed(clamped)
            self._history.append(
                SpeedChange(
                    old_speed=old,
                    new_speed=clamped,
                    at_virtual_ns=self._clock.current_virtual_ns(),
                ),
            )
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener(old, clamped)
        return clamped

    def subscribe(self, listener: SpeedChangeListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return _unsubscribe

    def history(self) -> tuple[SpeedChange, ...]:
        with self._lock:
            return tuple(self._history)

    def reset_history(self) -> None:
        with self._lock:
            self._history.clear()
