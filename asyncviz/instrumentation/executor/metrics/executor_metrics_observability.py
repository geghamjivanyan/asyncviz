"""Engine-level observability counters for executor metrics."""

from __future__ import annotations

import threading

from asyncviz.instrumentation.executor.metrics.executor_metrics_models import (
    ExecutorMetricsEngineSelfSnapshot,
)


class _EngineMetrics:
    __slots__ = (
        "_contention_detections",
        "_events_dropped",
        "_events_ignored",
        "_events_observed",
        "_executors_evicted",
        "_latency_spikes",
        "_lock",
        "_recursion_skips",
        "_saturation_transitions",
        "_tracked_executors",
        "_updates_emitted",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events_observed = 0
        self._events_ignored = 0
        self._events_dropped = 0
        self._updates_emitted = 0
        self._saturation_transitions = 0
        self._contention_detections = 0
        self._latency_spikes = 0
        self._tracked_executors = 0
        self._executors_evicted = 0
        self._recursion_skips = 0

    def record_observed(self) -> None:
        with self._lock:
            self._events_observed += 1

    def record_ignored(self) -> None:
        with self._lock:
            self._events_ignored += 1

    def record_dropped(self) -> None:
        with self._lock:
            self._events_dropped += 1

    def record_update_emitted(self) -> None:
        with self._lock:
            self._updates_emitted += 1

    def record_saturation_transition(self) -> None:
        with self._lock:
            self._saturation_transitions += 1

    def record_contention_detected(self) -> None:
        with self._lock:
            self._contention_detections += 1

    def record_latency_spike(self) -> None:
        with self._lock:
            self._latency_spikes += 1

    def record_executor_evicted(self) -> None:
        with self._lock:
            self._executors_evicted += 1

    def record_recursion_skip(self) -> None:
        with self._lock:
            self._recursion_skips += 1

    def set_tracked_executors(self, count: int) -> None:
        with self._lock:
            self._tracked_executors = count

    def snapshot(self) -> ExecutorMetricsEngineSelfSnapshot:
        with self._lock:
            return ExecutorMetricsEngineSelfSnapshot(
                events_observed=self._events_observed,
                events_ignored=self._events_ignored,
                events_dropped=self._events_dropped,
                updates_emitted=self._updates_emitted,
                saturation_transitions=self._saturation_transitions,
                contention_detections=self._contention_detections,
                latency_spike_detections=self._latency_spikes,
                tracked_executors=self._tracked_executors,
                executors_evicted=self._executors_evicted,
                recursion_skips=self._recursion_skips,
            )

    def reset(self) -> None:
        with self._lock:
            self._events_observed = 0
            self._events_ignored = 0
            self._events_dropped = 0
            self._updates_emitted = 0
            self._saturation_transitions = 0
            self._contention_detections = 0
            self._latency_spikes = 0
            self._tracked_executors = 0
            self._executors_evicted = 0
            self._recursion_skips = 0


_default_metrics = _EngineMetrics()


def get_executor_metrics_engine_metrics() -> _EngineMetrics:
    return _default_metrics


def reset_executor_metrics_engine_metrics() -> None:
    _default_metrics.reset()
