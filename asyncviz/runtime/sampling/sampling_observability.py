"""Process-wide sampling metrics."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SamplingMetricsSnapshot:
    samplers_started: int = 0
    samplers_reset: int = 0
    events_observed: int = 0
    events_retained: int = 0
    events_dropped: int = 0
    critical_retained: int = 0
    structural_retained: int = 0
    state_retained: int = 0
    delta_retained: int = 0
    dropped_by_rate: int = 0
    dropped_by_budget: int = 0
    dropped_by_overload: int = 0
    dropped_by_backpressure: int = 0
    adaptive_transitions: int = 0
    websocket_shed_engagements: int = 0
    websocket_shed_releases: int = 0
    markers_emitted: int = 0
    integrity_violations: int = 0


class _SamplingMetrics:
    __slots__ = (
        "_adaptive_transitions",
        "_critical_retained",
        "_delta_retained",
        "_dropped_by_backpressure",
        "_dropped_by_budget",
        "_dropped_by_overload",
        "_dropped_by_rate",
        "_events_dropped",
        "_events_observed",
        "_events_retained",
        "_integrity_violations",
        "_lock",
        "_markers_emitted",
        "_samplers_reset",
        "_samplers_started",
        "_state_retained",
        "_structural_retained",
        "_websocket_shed_engagements",
        "_websocket_shed_releases",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self._samplers_started = 0
        self._samplers_reset = 0
        self._events_observed = 0
        self._events_retained = 0
        self._events_dropped = 0
        self._critical_retained = 0
        self._structural_retained = 0
        self._state_retained = 0
        self._delta_retained = 0
        self._dropped_by_rate = 0
        self._dropped_by_budget = 0
        self._dropped_by_overload = 0
        self._dropped_by_backpressure = 0
        self._adaptive_transitions = 0
        self._websocket_shed_engagements = 0
        self._websocket_shed_releases = 0
        self._markers_emitted = 0
        self._integrity_violations = 0

    # ── mutators ──────────────────────────────────────────────────

    def record_sampler_started(self) -> None:
        with self._lock:
            self._samplers_started += 1

    def record_sampler_reset(self) -> None:
        with self._lock:
            self._samplers_reset += 1

    def record_observation(self, *, retained: bool) -> None:
        with self._lock:
            self._events_observed += 1
            if retained:
                self._events_retained += 1
            else:
                self._events_dropped += 1

    def record_retained_priority(self, name: str) -> None:
        with self._lock:
            if name == "critical":
                self._critical_retained += 1
            elif name == "structural":
                self._structural_retained += 1
            elif name == "state":
                self._state_retained += 1
            elif name == "delta":
                self._delta_retained += 1

    def record_drop_reason(self, reason: str) -> None:
        with self._lock:
            if reason == "dropped-by-rate":
                self._dropped_by_rate += 1
            elif reason == "dropped-by-budget":
                self._dropped_by_budget += 1
            elif reason == "dropped-by-overload":
                self._dropped_by_overload += 1
            elif reason == "dropped-by-backpressure":
                self._dropped_by_backpressure += 1

    def record_adaptive_transition(self) -> None:
        with self._lock:
            self._adaptive_transitions += 1

    def record_websocket_shed(self, *, engaged: bool) -> None:
        with self._lock:
            if engaged:
                self._websocket_shed_engagements += 1
            else:
                self._websocket_shed_releases += 1

    def record_marker_emitted(self) -> None:
        with self._lock:
            self._markers_emitted += 1

    def record_integrity_violation(self) -> None:
        with self._lock:
            self._integrity_violations += 1

    def snapshot(self) -> SamplingMetricsSnapshot:
        with self._lock:
            return SamplingMetricsSnapshot(
                samplers_started=self._samplers_started,
                samplers_reset=self._samplers_reset,
                events_observed=self._events_observed,
                events_retained=self._events_retained,
                events_dropped=self._events_dropped,
                critical_retained=self._critical_retained,
                structural_retained=self._structural_retained,
                state_retained=self._state_retained,
                delta_retained=self._delta_retained,
                dropped_by_rate=self._dropped_by_rate,
                dropped_by_budget=self._dropped_by_budget,
                dropped_by_overload=self._dropped_by_overload,
                dropped_by_backpressure=self._dropped_by_backpressure,
                adaptive_transitions=self._adaptive_transitions,
                websocket_shed_engagements=self._websocket_shed_engagements,
                websocket_shed_releases=self._websocket_shed_releases,
                markers_emitted=self._markers_emitted,
                integrity_violations=self._integrity_violations,
            )

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()


_METRICS: _SamplingMetrics | None = None
_METRICS_LOCK = threading.Lock()


def get_sampling_metrics() -> _SamplingMetrics:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = _SamplingMetrics()
    return _METRICS


def get_sampling_metrics_snapshot() -> SamplingMetricsSnapshot:
    return get_sampling_metrics().snapshot()


def reset_sampling_metrics() -> None:
    if _METRICS is not None:
        _METRICS.reset()
