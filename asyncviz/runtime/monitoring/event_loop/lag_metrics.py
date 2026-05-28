"""Lifetime counters + self-observability for the lag monitor.

Distinct from :mod:`lag_statistics`, which aggregates *measurements*:
this module tracks *meta* — how the monitor itself is performing
(samples produced, drops, scheduler drift, threshold hits, events
emitted). Snapshots are returned by :meth:`EventLoopLagMonitor.metrics_snapshot`
for the dashboard's /api/runtime/monitoring/lag endpoint.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagSeverity


@dataclass(frozen=True, slots=True)
class LagMetricsSnapshot:
    """Immutable view of the monitor's lifetime self-metrics."""

    samples_attempted: int
    samples_recorded: int
    samples_dropped: int
    consecutive_drops: int
    max_consecutive_drops_observed: int
    scheduler_drift_ns: int
    warning_threshold_hits: int
    critical_threshold_hits: int
    freeze_threshold_hits: int
    measurement_events_emitted: int
    measurement_events_dropped: int
    threshold_breach_events_emitted: int
    sampler_invocations: int
    sampler_failures: int
    reconfigurations: int

    def to_dict(self) -> dict[str, int]:
        return {
            "samples_attempted": self.samples_attempted,
            "samples_recorded": self.samples_recorded,
            "samples_dropped": self.samples_dropped,
            "consecutive_drops": self.consecutive_drops,
            "max_consecutive_drops_observed": self.max_consecutive_drops_observed,
            "scheduler_drift_ns": self.scheduler_drift_ns,
            "warning_threshold_hits": self.warning_threshold_hits,
            "critical_threshold_hits": self.critical_threshold_hits,
            "freeze_threshold_hits": self.freeze_threshold_hits,
            "measurement_events_emitted": self.measurement_events_emitted,
            "measurement_events_dropped": self.measurement_events_dropped,
            "threshold_breach_events_emitted": self.threshold_breach_events_emitted,
            "sampler_invocations": self.sampler_invocations,
            "sampler_failures": self.sampler_failures,
            "reconfigurations": self.reconfigurations,
        }


class LagMetrics:
    """Mutable lifetime counters; snapshots via :meth:`snapshot`.

    Every increment is guarded by a single lock — the counters are
    touched once per sample, so contention is negligible. Reset is
    intentionally *not* provided: lifetime counters survive monitor
    restarts because operators want them for postmortems.
    """

    __slots__ = (
        "_consecutive_drops",
        "_critical_hits",
        "_freeze_hits",
        "_lock",
        "_max_consecutive_drops_observed",
        "_measurement_events_dropped",
        "_measurement_events_emitted",
        "_reconfigurations",
        "_sampler_failures",
        "_sampler_invocations",
        "_samples_attempted",
        "_samples_dropped",
        "_samples_recorded",
        "_scheduler_drift_ns",
        "_threshold_breach_events_emitted",
        "_warning_hits",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._samples_attempted = 0
        self._samples_recorded = 0
        self._samples_dropped = 0
        self._consecutive_drops = 0
        self._max_consecutive_drops_observed = 0
        self._scheduler_drift_ns = 0
        self._warning_hits = 0
        self._critical_hits = 0
        self._freeze_hits = 0
        self._measurement_events_emitted = 0
        self._measurement_events_dropped = 0
        self._threshold_breach_events_emitted = 0
        self._sampler_invocations = 0
        self._sampler_failures = 0
        self._reconfigurations = 0

    # ── sample lifecycle ─────────────────────────────────────────────────
    def record_sample_attempted(self) -> None:
        with self._lock:
            self._samples_attempted += 1

    def record_sample_recorded(self) -> None:
        with self._lock:
            self._samples_recorded += 1
            self._consecutive_drops = 0

    def record_sample_dropped(self) -> None:
        with self._lock:
            self._samples_dropped += 1
            self._consecutive_drops += 1
            if self._consecutive_drops > self._max_consecutive_drops_observed:
                self._max_consecutive_drops_observed = self._consecutive_drops

    # ── scheduler ────────────────────────────────────────────────────────
    def record_scheduler_drift(self, drift_ns: int) -> None:
        if drift_ns <= 0:
            return
        with self._lock:
            self._scheduler_drift_ns += drift_ns

    # ── threshold ────────────────────────────────────────────────────────
    def record_threshold_hit(self, severity: LagSeverity) -> None:
        with self._lock:
            if severity >= LagSeverity.WARNING:
                self._warning_hits += 1
            if severity >= LagSeverity.CRITICAL:
                self._critical_hits += 1
            if severity >= LagSeverity.FREEZE:
                self._freeze_hits += 1

    # ── events ───────────────────────────────────────────────────────────
    def record_measurement_event(self) -> None:
        with self._lock:
            self._measurement_events_emitted += 1

    def record_measurement_event_dropped(self) -> None:
        with self._lock:
            self._measurement_events_dropped += 1

    def record_threshold_breach_event(self) -> None:
        with self._lock:
            self._threshold_breach_events_emitted += 1

    # ── sampler ──────────────────────────────────────────────────────────
    def record_sampler_invocation(self) -> None:
        with self._lock:
            self._sampler_invocations += 1

    def record_sampler_failure(self) -> None:
        with self._lock:
            self._sampler_failures += 1

    # ── lifecycle ────────────────────────────────────────────────────────
    def record_reconfiguration(self) -> None:
        with self._lock:
            self._reconfigurations += 1

    # ── snapshot ─────────────────────────────────────────────────────────
    def snapshot(self) -> LagMetricsSnapshot:
        with self._lock:
            return LagMetricsSnapshot(
                samples_attempted=self._samples_attempted,
                samples_recorded=self._samples_recorded,
                samples_dropped=self._samples_dropped,
                consecutive_drops=self._consecutive_drops,
                max_consecutive_drops_observed=self._max_consecutive_drops_observed,
                scheduler_drift_ns=self._scheduler_drift_ns,
                warning_threshold_hits=self._warning_hits,
                critical_threshold_hits=self._critical_hits,
                freeze_threshold_hits=self._freeze_hits,
                measurement_events_emitted=self._measurement_events_emitted,
                measurement_events_dropped=self._measurement_events_dropped,
                threshold_breach_events_emitted=self._threshold_breach_events_emitted,
                sampler_invocations=self._sampler_invocations,
                sampler_failures=self._sampler_failures,
                reconfigurations=self._reconfigurations,
            )
