"""Pressure scoring + level classification.

The pressure score is a small composite in ``[0.0, 1.0]``:

* ``occupancy_ratio`` (weighted 0.55) — how full is the queue right now?
* ``blocked_ratio`` (weighted 0.30) — soft normalization of the blocked
  producer+consumer count (caps at 16 blocked tasks).
* ``backlog_velocity_ratio`` (weighted 0.15) — magnitude of
  ``put_rate - get_rate`` divided by ``put_rate + get_rate``; captures
  whether the queue is filling or draining.

Hysteresis is enforced at *level transition* time, not at score time:
the raw score doesn't lie, but the published level only changes when
the score is firmly inside (or outside) the band.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.instrumentation.queue.metrics.queue_metrics_configuration import (
    QueueMetricsConfig,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    PressureLevel,
    QueuePressureSnapshot,
)

_BLOCKED_NORMALIZATION_CAP = 16
"""Number of blocked tasks at which the ``blocked_ratio`` contribution
saturates at 1.0. Past this point the queue is unambiguously contended;
adding more blocked tasks doesn't make the situation meaningfully worse
from a *score-shape* perspective."""


@dataclass(slots=True)
class PressureScorer:
    config: QueueMetricsConfig
    level: PressureLevel = "calm"
    saturated: bool = False
    """Sticky bit — flipped on saturation_detected, cleared when occupancy
    falls below the recovery threshold. Lets the engine fire one event
    per saturation crossing."""

    last_score: float = 0.0
    saturation_ratio: float = 0.0
    last_backlog_velocity: float = 0.0

    def evaluate(
        self,
        *,
        occupancy_ratio: float,
        blocked_producers: int,
        blocked_consumers: int,
        put_rate: float,
        get_rate: float,
    ) -> QueuePressureSnapshot:
        """Compute the score + classify into a level (with hysteresis)."""
        score = self._compute_score(
            occupancy_ratio=occupancy_ratio,
            blocked_producers=blocked_producers,
            blocked_consumers=blocked_consumers,
            put_rate=put_rate,
            get_rate=get_rate,
        )
        new_level = self._classify(score)
        backlog_velocity = put_rate - get_rate

        self.last_score = score
        self.last_backlog_velocity = backlog_velocity
        if occupancy_ratio > self.saturation_ratio:
            self.saturation_ratio = occupancy_ratio
        self.level = new_level

        return QueuePressureSnapshot(
            pressure_score=score,
            level=new_level,
            saturation_ratio=self.saturation_ratio,
            saturated=self.saturated,
            backlog_velocity=backlog_velocity,
        )

    def mark_saturated(self, *, saturated: bool) -> None:
        self.saturated = saturated

    def _compute_score(
        self,
        *,
        occupancy_ratio: float,
        blocked_producers: int,
        blocked_consumers: int,
        put_rate: float,
        get_rate: float,
    ) -> float:
        occupancy = max(0.0, min(1.0, occupancy_ratio))
        blocked_total = blocked_producers + blocked_consumers
        blocked_ratio = min(1.0, blocked_total / _BLOCKED_NORMALIZATION_CAP)
        total_rate = put_rate + get_rate
        if total_rate <= 0.0:
            velocity_ratio = 0.0
        else:
            velocity_ratio = min(1.0, abs(put_rate - get_rate) / total_rate)
        score = (occupancy * 0.55) + (blocked_ratio * 0.30) + (velocity_ratio * 0.15)
        # Numerical safety — single-precision drift shouldn't push us out.
        return max(0.0, min(1.0, score))

    def _classify(self, score: float) -> PressureLevel:
        warn = self.config.pressure_warning_threshold
        crit = self.config.pressure_critical_threshold
        hyst = self.config.pressure_hysteresis
        if self.level == "calm":
            if score >= crit:
                return "critical"
            if score >= warn:
                return "warning"
            return "calm"
        if self.level == "warning":
            if score >= crit:
                return "critical"
            if score < warn - hyst:
                return "calm"
            return "warning"
        # critical
        if score < crit - hyst:
            return "warning" if score >= warn - hyst else "calm"
        return "critical"

    def reset(self) -> None:
        self.level = "calm"
        self.saturated = False
        self.last_score = 0.0
        self.saturation_ratio = 0.0
        self.last_backlog_velocity = 0.0
