"""Pause / resume controller.

Wraps the clock's ``pause``/``resume`` plus an :class:`asyncio.Event`
that the playback loop awaits — clean way to suspend an async loop
without busy-waiting. Idempotent in both directions: pausing a
paused engine is a no-op; resuming a running one is too.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.replay.runtime.replay_clock import ReplayClock

PauseListener = Callable[[bool], None]
"""``listener(now_paused: bool)``. Fired after every transition."""


@dataclass(frozen=True, slots=True)
class PauseTransition:
    paused: bool
    at_virtual_ns: int


class PauseController:
    """Coordinates pause/resume state across the engine."""

    __slots__ = ("_clock", "_event", "_history", "_listeners", "_lock")

    def __init__(self, clock: ReplayClock) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._event = asyncio.Event()
        self._event.set()  # initial state: NOT paused
        self._listeners: list[PauseListener] = []
        self._history: list[PauseTransition] = []

    @property
    def paused(self) -> bool:
        return self._clock.paused

    def pause(self) -> bool:
        """Pause the engine. Returns True if the call actually
        flipped state, False if already paused."""
        with self._lock:
            if self._clock.paused:
                return False
            self._clock.pause()
            self._event.clear()
            self._history.append(
                PauseTransition(paused=True, at_virtual_ns=self._clock.current_virtual_ns()),
            )
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener(True)
        return True

    def resume(self) -> bool:
        with self._lock:
            if not self._clock.paused:
                return False
            self._clock.resume()
            self._event.set()
            self._history.append(
                PauseTransition(
                    paused=False, at_virtual_ns=self._clock.current_virtual_ns(),
                ),
            )
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener(False)
        return True

    async def wait_until_running(self) -> None:
        """Suspend the calling coroutine until the engine is not paused."""
        await self._event.wait()

    def subscribe(self, listener: PauseListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return _unsubscribe

    def history(self) -> tuple[PauseTransition, ...]:
        with self._lock:
            return tuple(self._history)
