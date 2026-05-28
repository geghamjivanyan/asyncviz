"""State store — atomic swap, listener fan-out.

Holds the current :class:`VirtualRuntimeState`. Mutations go through
:meth:`update`, which:

1. Computes the next state via a caller-supplied function.
2. Atomically swaps the current state under a lock.
3. Fans the new state out to subscribers.

Subscribers don't *block* the engine — they're called outside the
lock and any exception in a listener is logged + isolated so a
buggy subscriber can't break replay."""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import suppress

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.utils.logging import get_logger

logger = get_logger("replay.runtime.state_store")

StateListener = Callable[[VirtualRuntimeState, VirtualRuntimeState], None]
"""``listener(previous_state, next_state)``."""


class ReplayStateStore:
    """Thread-safe holder for the current virtual runtime state."""

    __slots__ = ("_listeners", "_lock", "_state")

    def __init__(self, initial: VirtualRuntimeState | None = None) -> None:
        self._lock = threading.RLock()
        self._state = initial or VirtualRuntimeState.empty()
        self._listeners: list[StateListener] = []

    # ── readers ───────────────────────────────────────────────────

    @property
    def state(self) -> VirtualRuntimeState:
        with self._lock:
            return self._state

    # ── mutators ──────────────────────────────────────────────────

    def update(
        self, fn: Callable[[VirtualRuntimeState], VirtualRuntimeState],
    ) -> VirtualRuntimeState:
        """Run ``fn(state) -> next_state`` under the lock + swap."""
        with self._lock:
            previous = self._state
            next_state = fn(previous)
            if next_state is previous:
                return previous
            self._state = next_state
            listeners = tuple(self._listeners)
        for listener in listeners:
            with suppress(Exception):
                listener(previous, next_state)
        return next_state

    def replace(self, state: VirtualRuntimeState) -> VirtualRuntimeState:
        """Atomic replacement (used by snapshot restore + seek)."""
        with self._lock:
            previous = self._state
            self._state = state
            listeners = tuple(self._listeners)
        for listener in listeners:
            with suppress(Exception):
                listener(previous, state)
        return state

    # ── listeners ─────────────────────────────────────────────────

    def subscribe(self, listener: StateListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return _unsubscribe
