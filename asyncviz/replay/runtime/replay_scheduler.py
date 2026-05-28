"""Replay frame scheduler.

Given the next frame's virtual timestamp + the current clock state,
compute how long the engine should defer dispatch. Three modes:

* ``realtime`` — honor the gap. Cap the wait at the catch-up
  threshold so a long pause + resume doesn't immediately produce a
  multi-minute sleep.
* ``as_fast_as_possible`` — always return zero. Bulk catch-up,
  state-warm-up, headless tests.
* ``step`` — always return zero; the playback controller invokes
  the scheduler manually per step.

The scheduler is *stateless* — every call independently consults
the clock. That's deliberate: the clock is the only source of
truth, so a missed wakeup or a speed change between two scheduler
calls produces a correct (newly computed) delay rather than a stale
one based on cached state.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.replay_clock import ReplayClock
from asyncviz.replay.runtime.replay_configuration import PlaybackMode


@dataclass(frozen=True, slots=True)
class FrameSchedule:
    """One scheduled dispatch."""

    wait_seconds: float
    """How long the engine should sleep before dispatch. 0 means
    'fire immediately'."""

    behind_by_ns: int
    """Positive if the engine is behind (catch-up mode), 0 if on
    time, negative if it would be ahead (scheduled delay)."""

    target_virtual_ns: int
    """The frame's virtual timestamp — useful for trace + metrics."""


class ReplayScheduler:
    """Computes per-frame dispatch delays."""

    __slots__ = ("_catch_up_threshold_ns", "_clock", "_mode")

    def __init__(
        self,
        clock: ReplayClock,
        *,
        mode: PlaybackMode = "realtime",
        catch_up_threshold_seconds: float = 0.5,
    ) -> None:
        self._clock = clock
        self._mode = mode
        self._catch_up_threshold_ns = int(catch_up_threshold_seconds * 1e9)

    @property
    def mode(self) -> PlaybackMode:
        return self._mode

    def set_mode(self, mode: PlaybackMode) -> None:
        self._mode = mode

    def schedule(self, frame_monotonic_ns: int) -> FrameSchedule:
        """Plan the next dispatch."""
        target = int(frame_monotonic_ns)
        if self._mode in ("as_fast_as_possible", "step"):
            return FrameSchedule(
                wait_seconds=0.0,
                behind_by_ns=0,
                target_virtual_ns=target,
            )
        # Realtime mode.
        current = self._clock.current_virtual_ns()
        delta_ns = target - current
        if delta_ns <= 0:
            # Engine is at or past the target — fire immediately.
            return FrameSchedule(
                wait_seconds=0.0,
                behind_by_ns=-delta_ns,
                target_virtual_ns=target,
            )
        # Cap the wait to prevent silly multi-minute sleeps when a
        # pause + resume hands us a huge delta.
        if self._catch_up_threshold_ns > 0 and delta_ns > self._catch_up_threshold_ns:
            wait_ns = self._catch_up_threshold_ns
        else:
            wait_ns = delta_ns
        wait_seconds = wait_ns / 1e9
        speed = self._clock.speed
        if speed > 0:
            wait_seconds = wait_seconds / speed
        return FrameSchedule(
            wait_seconds=max(0.0, wait_seconds),
            behind_by_ns=0,
            target_virtual_ns=target,
        )
