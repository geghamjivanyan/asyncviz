"""Drift-resistant clock-scaling coordinator.

Wraps :class:`ReplayClock` for the speed coordinator's needs:

1. **Atomic re-anchoring** — each speed change is one
   ``set_speed`` call on the clock, which already re-anchors
   ``(wall_anchor_ns, virtual_anchor_ns)``. Virtual time observed
   right before + right after the change is identical.

2. **Drift tracking** — the coordinator periodically samples
   virtual time and compares against the *expected* progression
   from the initial anchor. Drift = ``observed - expected``. The
   clock primitive doesn't itself accumulate drift; this is a
   *correctness check* that catches external interference (other
   code calling ``set_speed`` directly, a system clock jump, etc.).

3. **Anchor snapshots** — for diagnostics + collaborative replay
   bootstrapping.

The wall-clock source is pluggable so tests can drive both the
underlying :class:`ReplayClock` and the coordinator from the same
deterministic counter.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.replay.runtime.replay_clock import ReplayClock

WallClockFn = Callable[[], int]


@dataclass(frozen=True, slots=True)
class ClockScalingAnchor:
    """Snapshot of clock state after a speed transition."""

    speed: float
    virtual_ns: int
    wall_ns: int
    paused: bool


@dataclass(frozen=True, slots=True)
class DriftSample:
    """One observed-vs-expected sample."""

    observed_virtual_ns: int
    expected_virtual_ns: int
    drift_ns: int
    at_wall_ns: int


class SpeedClockCoordinator:
    """Owns the clock side of every speed change."""

    __slots__ = ("_anchor", "_clock", "_wall_clock")

    def __init__(
        self,
        clock: ReplayClock,
        *,
        wall_clock: WallClockFn | None = None,
    ) -> None:
        self._clock = clock
        self._wall_clock: WallClockFn = wall_clock or time.monotonic_ns
        self._anchor = ClockScalingAnchor(
            speed=clock.speed,
            virtual_ns=clock.current_virtual_ns(),
            wall_ns=self._wall_clock(),
            paused=clock.paused,
        )

    @property
    def anchor(self) -> ClockScalingAnchor:
        return self._anchor

    @property
    def current_speed(self) -> float:
        return self._clock.speed

    def apply_speed(self, new_speed: float) -> ClockScalingAnchor:
        """Install ``new_speed`` on the clock + refresh the anchor."""
        if new_speed <= 0:
            raise ValueError(f"speed must be > 0 (got {new_speed})")
        self._clock.set_speed(new_speed)
        self._anchor = ClockScalingAnchor(
            speed=self._clock.speed,
            virtual_ns=self._clock.current_virtual_ns(),
            wall_ns=self._wall_clock(),
            paused=self._clock.paused,
        )
        return self._anchor

    def sample_drift(self) -> DriftSample:
        """Compare observed virtual time against the expected
        progression from the anchor."""
        anchor = self._anchor
        now_wall = self._wall_clock()
        elapsed_wall = max(0, now_wall - anchor.wall_ns)
        if anchor.paused or self._clock.paused:
            expected = anchor.virtual_ns
        else:
            expected = anchor.virtual_ns + int(elapsed_wall * anchor.speed)
        observed = self._clock.current_virtual_ns()
        return DriftSample(
            observed_virtual_ns=observed,
            expected_virtual_ns=expected,
            drift_ns=observed - expected,
            at_wall_ns=now_wall,
        )

    def re_anchor_from_seek(self, virtual_ns: int) -> ClockScalingAnchor:
        """Refresh the anchor after a seek re-anchors the clock. The
        coordinator calls this so subsequent drift samples don't
        flag the seek as drift."""
        self._anchor = ClockScalingAnchor(
            speed=self._clock.speed,
            virtual_ns=int(virtual_ns),
            wall_ns=self._wall_clock(),
            paused=self._clock.paused,
        )
        return self._anchor
