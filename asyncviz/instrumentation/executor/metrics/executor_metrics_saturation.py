"""Saturation scoring + level classification for executors.

Composite score in ``[0.0, 1.0]``:

* ``utilization_ratio`` (weighted 0.55) — workers in use vs cap.
* ``backlog_ratio`` (weighted 0.25) — soft normalization of the
  current backlog (caps at ``max_workers * 4`` so a small overshoot
  is "warning" but a 100-deep queue is full critical).
* ``latency_pressure`` (weighted 0.20) — mean submission latency
  normalized by a configurable scale (defaults to 100ms saturation).

Hysteresis: published level only changes when the score is firmly
inside (or outside) the band — same pattern as the queue + semaphore
analytics.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.instrumentation.executor.metrics.executor_metrics_configuration import (
    ExecutorMetricsConfig,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_models import (
    ExecutorSaturationSnapshot,
    SaturationLevel,
)

LATENCY_NORMALIZATION_SECONDS = 0.1
"""Submission latency at which the latency component contributes 1.0.
Tuned so a 100ms queue time saturates the pressure dimension — beyond
this point we can't add more "pressure" via latency alone, only via
utilization + backlog."""

BACKLOG_NORMALIZATION_FACTOR = 4
"""Backlog at which the backlog component contributes 1.0, expressed
as a multiple of ``max_workers``. A 4x overshoot indicates the pool is
significantly behind."""


@dataclass(slots=True)
class SaturationScorer:
    config: ExecutorMetricsConfig
    level: SaturationLevel = "calm"
    peak_utilization_ratio: float = 0.0
    last_score: float = 0.0
    last_backlog_velocity: float = 0.0

    def evaluate(
        self,
        *,
        utilization_ratio: float,
        max_workers: int | None,
        backlog: int,
        submission_rate: float,
        completion_rate: float,
        mean_submission_latency: float,
    ) -> ExecutorSaturationSnapshot:
        score = self._compute_score(
            utilization_ratio=utilization_ratio,
            max_workers=max_workers,
            backlog=backlog,
            mean_submission_latency=mean_submission_latency,
        )
        backlog_velocity = submission_rate - completion_rate
        if utilization_ratio > self.peak_utilization_ratio:
            self.peak_utilization_ratio = utilization_ratio
        self.last_score = score
        self.last_backlog_velocity = backlog_velocity
        self.level = self._classify(score)
        return ExecutorSaturationSnapshot(
            saturation_score=score,
            level=self.level,
            peak_utilization_ratio=self.peak_utilization_ratio,
            backlog_velocity=backlog_velocity,
        )

    def _compute_score(
        self,
        *,
        utilization_ratio: float,
        max_workers: int | None,
        backlog: int,
        mean_submission_latency: float,
    ) -> float:
        util = max(0.0, min(1.0, utilization_ratio))
        if max_workers and max_workers > 0:
            backlog_norm = min(1.0, backlog / (max_workers * BACKLOG_NORMALIZATION_FACTOR))
        else:
            backlog_norm = 0.0
        if mean_submission_latency <= 0.0:
            latency_norm = 0.0
        else:
            latency_norm = min(1.0, mean_submission_latency / LATENCY_NORMALIZATION_SECONDS)
        score = (util * 0.55) + (backlog_norm * 0.25) + (latency_norm * 0.20)
        return max(0.0, min(1.0, score))

    def _classify(self, score: float) -> SaturationLevel:
        warn = self.config.saturation_warning_threshold
        crit = self.config.saturation_critical_threshold
        hyst = self.config.saturation_hysteresis
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
        self.peak_utilization_ratio = 0.0
        self.last_score = 0.0
        self.last_backlog_velocity = 0.0
