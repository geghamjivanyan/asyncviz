"""Scheduler adapter for the speed coordinator.

The runtime scheduler is stateless w.r.t. speed — every dispatch
re-queries the clock — so this adapter is intentionally tiny. It
exists so the coordinator can express scheduler-related concerns
without poking at the scheduler directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.replay_scheduler import ReplayScheduler


@dataclass(slots=True)
class SpeedSchedulerCoordinator:
    """Thin adapter — the scheduler doesn't currently store speed,
    so this is here to formalize the integration point for future
    enhancements (e.g. mode-flip during speed transitions)."""

    scheduler: ReplayScheduler

    @property
    def mode(self) -> str:
        return self.scheduler.mode

    def note_speed_change(self, new_speed: float) -> None:
        """No-op today — the scheduler always queries the clock for
        the current speed. Reserved for future modes that may want
        to pre-compute schedules under the new speed."""
        # Reserved for future adaptive-pacing extensions.
        _ = new_speed
