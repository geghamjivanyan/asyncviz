"""Atomic transition primitive.

One ``apply`` call:

1. Records the *before* state.
2. Re-anchors the clock.
3. Notifies the scheduler.
4. Records the *after* state.
5. Returns a :class:`SpeedTransition` for the history ring.

The primitive is sync because the only operations involved are
in-process. Async coordination (queueing, awaitable barriers) lives
at the coordinator layer above.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from asyncviz.replay.runtime.speed.models.speed_request import (
    SpeedChangeRequest,
    SpeedTransition,
)
from asyncviz.replay.runtime.speed.replay_speed_clock import (
    SpeedClockCoordinator,
)
from asyncviz.replay.runtime.speed.replay_speed_scheduler import (
    SpeedSchedulerCoordinator,
)


@dataclass(slots=True)
class SpeedTransitionEngine:
    """Applies one speed transition atomically."""

    clock: SpeedClockCoordinator
    scheduler: SpeedSchedulerCoordinator

    def apply(
        self,
        *,
        request: SpeedChangeRequest,
        resolved_speed: float,
    ) -> SpeedTransition:
        """Install ``resolved_speed`` on the clock + return the
        :class:`SpeedTransition` record."""
        started_ns = time.monotonic_ns()
        previous = self.clock.current_speed
        anchor = self.clock.apply_speed(resolved_speed)
        self.scheduler.note_speed_change(resolved_speed)
        ended_ns = time.monotonic_ns()
        return SpeedTransition(
            request_id=request.request_id,
            previous_speed=previous,
            new_speed=anchor.speed,
            at_virtual_ns=anchor.virtual_ns,
            at_wall_ns=anchor.wall_ns,
            latency_ns=max(0, ended_ns - started_ns),
            reason=request.reason,
        )
