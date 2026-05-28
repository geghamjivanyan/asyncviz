"""Scheduler coordination for seek transitions.

The runtime scheduler is stateless w.r.t. seeks — every dispatch
re-queries the clock — so this adapter is intentionally tiny. It
exists so the coordinator can express seek-related scheduler tweaks
(switch to as_fast_as_possible during background reconstruction)
without poking at the scheduler directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.replay_configuration import PlaybackMode
from asyncviz.replay.runtime.replay_scheduler import ReplayScheduler


@dataclass(slots=True)
class SeekSchedulerCoordinator:
    """Captures + restores the scheduler's mode around a seek."""

    scheduler: ReplayScheduler
    _saved_mode: PlaybackMode | None = None

    def enter_background_reconstruction(self) -> None:
        """Switch the scheduler to ``as_fast_as_possible`` so the
        engine doesn't sleep between reconstruction frames."""
        if self._saved_mode is None:
            self._saved_mode = self.scheduler.mode
        self.scheduler.set_mode("as_fast_as_possible")

    def restore_normal_mode(self) -> None:
        """Re-install the scheduler mode captured by
        :meth:`enter_background_reconstruction`."""
        if self._saved_mode is not None:
            self.scheduler.set_mode(self._saved_mode)
            self._saved_mode = None
