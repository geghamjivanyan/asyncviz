"""Scheduler awareness for pause/resume.

The scheduler in the runtime layer is *stateless* — it doesn't need
to be informed about pause / resume because every call re-queries
the clock. But the coordinator wants to:

1. Switch the scheduler into ``step`` mode during single-frame
   coordination so the engine loop dispatches exactly one frame and
   then re-pauses.
2. Switch back to the configured normal mode (``realtime`` or
   ``as_fast_as_possible``) when stepping finishes.

This adapter encapsulates the mode-flip choreography so the
coordinator + the scheduler stay decoupled.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.replay_configuration import PlaybackMode
from asyncviz.replay.runtime.replay_scheduler import ReplayScheduler


@dataclass(slots=True)
class SchedulerCoordinator:
    """Owns the scheduler's mode transitions for stepping."""

    scheduler: ReplayScheduler
    _normal_mode: PlaybackMode | None = None

    @property
    def mode(self) -> PlaybackMode:
        return self.scheduler.mode

    def begin_step(self) -> None:
        """Capture the normal mode + switch to step mode."""
        if self._normal_mode is None:
            self._normal_mode = self.scheduler.mode
        self.scheduler.set_mode("step")

    def end_step(self) -> None:
        """Restore the previously-captured normal mode."""
        if self._normal_mode is not None:
            self.scheduler.set_mode(self._normal_mode)
            self._normal_mode = None

    def set_normal_mode(self, mode: PlaybackMode) -> None:
        """Update the *captured* normal mode without changing the
        scheduler's current mode. Used when an external caller
        changes playback mode while we're stepping."""
        self._normal_mode = mode
