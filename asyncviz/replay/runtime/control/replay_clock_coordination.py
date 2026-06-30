"""Clock coordination for pause/resume.

The :class:`ReplayClock` already knows how to ``pause`` and
``resume``. This module is a small adapter that:

1. Tracks the virtual time the clock was at when paused, so the
   coordinator can report it back to callers (telemetry, UI).
2. Re-anchors the clock on resume in one atomic step so the
   virtual time observed before + after the pause are identical.
3. Records the pause/resume span lengths for diagnostics.

It's deliberately stateless beyond the most recent paused virtual
time — the clock itself owns durable state."""

from __future__ import annotations

import time
from dataclasses import dataclass

from asyncviz.replay.runtime.replay_clock import ReplayClock


@dataclass(slots=True)
class ClockPauseState:
    """Snapshot of the clock at the moment of pause."""

    paused_at_virtual_ns: int
    paused_at_wall_ns: int


@dataclass(slots=True)
class ClockResumeState:
    """Snapshot of the clock at the moment of resume."""

    resumed_at_virtual_ns: int
    resumed_at_wall_ns: int
    pause_duration_wall_ns: int


class ClockCoordinator:
    """Owns the ``clock.pause`` / ``clock.resume`` choreography."""

    __slots__ = ("_clock", "_pause_state")

    def __init__(self, clock: ReplayClock) -> None:
        self._clock = clock
        self._pause_state: ClockPauseState | None = None

    @property
    def paused(self) -> bool:
        return self._clock.paused

    @property
    def last_pause_state(self) -> ClockPauseState | None:
        return self._pause_state

    def pause(self) -> ClockPauseState:
        """Pause the clock + capture the pause anchor."""
        if not self._clock.paused:
            self._clock.pause()
        state = ClockPauseState(
            paused_at_virtual_ns=self._clock.current_virtual_ns(),
            paused_at_wall_ns=time.monotonic_ns(),
        )
        self._pause_state = state
        return state

    def resume(self) -> ClockResumeState:
        """Resume the clock + compute the pause duration."""
        previous = self._pause_state
        if self._clock.paused:
            self._clock.resume()
        now_wall = time.monotonic_ns()
        state = ClockResumeState(
            resumed_at_virtual_ns=self._clock.current_virtual_ns(),
            resumed_at_wall_ns=now_wall,
            pause_duration_wall_ns=(now_wall - previous.paused_at_wall_ns if previous else 0),
        )
        self._pause_state = None
        return state

    def jump_to(self, virtual_ns: int) -> None:
        """Re-anchor the clock at ``virtual_ns`` — used after a seek
        finishes inside a paused coordinator (the engine wants its
        virtual time to match the seek target on the next resume)."""
        self._clock.jump_to(virtual_ns)
        # If we were paused, refresh the snapshot so subsequent
        # resume reports use the seek target as the anchor.
        if self._pause_state is not None:
            self._pause_state = ClockPauseState(
                paused_at_virtual_ns=virtual_ns,
                paused_at_wall_ns=self._pause_state.paused_at_wall_ns,
            )
