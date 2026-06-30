"""Thread-safe holder for the coordinator's current phase.

Holds :class:`PlaybackPhaseSnapshot`; mutations go through
:meth:`transition_to`, which:

1. Validates the transition via :class:`ReplayTransitionGuard`.
2. Swaps the snapshot under a lock.
3. Notifies subscribers outside the lock (listener exceptions are
   isolated so a buggy subscriber can't deadlock the coordinator).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import suppress

from asyncviz.replay.runtime.control.models.playback_phase import (
    PlaybackPhase,
    PlaybackPhaseSnapshot,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("replay.runtime.control.state")

PhaseListener = Callable[[PlaybackPhaseSnapshot, PlaybackPhaseSnapshot], None]
"""``listener(previous, next)``."""


class PhaseTransitionError(RuntimeError):
    """Raised when a transition is illegal under strict mode."""


class ReplayPlaybackStateHolder:
    """Holds the current playback-phase snapshot + fans transitions
    out to subscribers."""

    __slots__ = ("_listeners", "_lock", "_state")

    def __init__(
        self,
        initial: PlaybackPhaseSnapshot | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._state = initial or PlaybackPhaseSnapshot(
            phase=PlaybackPhase.IDLE,
            last_sequence=0,
            last_monotonic_ns=0,
        )
        self._listeners: list[PhaseListener] = []

    # ── readers ───────────────────────────────────────────────────

    @property
    def snapshot(self) -> PlaybackPhaseSnapshot:
        with self._lock:
            return self._state

    @property
    def phase(self) -> PlaybackPhase:
        with self._lock:
            return self._state.phase

    # ── mutators ──────────────────────────────────────────────────

    def transition_to(
        self,
        next_snapshot: PlaybackPhaseSnapshot,
    ) -> PlaybackPhaseSnapshot:
        """Swap the snapshot atomically + notify listeners."""
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

    def update_position(
        self,
        *,
        last_sequence: int,
        last_monotonic_ns: int,
    ) -> PlaybackPhaseSnapshot:
        """Update only the cursor fields — used by the playback loop
        as it advances. Phase stays put."""
        with self._lock:
            previous = self._state
            if (
                previous.last_sequence == last_sequence
                and previous.last_monotonic_ns == last_monotonic_ns
            ):
                return previous
            self._state = PlaybackPhaseSnapshot(
                phase=previous.phase,
                last_sequence=last_sequence,
                last_monotonic_ns=last_monotonic_ns,
                pause_request_id=previous.pause_request_id,
                resume_request_id=previous.resume_request_id,
                error_detail=previous.error_detail,
            )
            listeners = tuple(self._listeners)
        for listener in listeners:
            with suppress(Exception):
                listener(previous, self._state)
        return self._state

    # ── listeners ─────────────────────────────────────────────────

    def subscribe(self, listener: PhaseListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return _unsubscribe
