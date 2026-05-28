"""Engine-level observability counters.

Mirrors the pattern used by the queue instrumentation's
:mod:`queue_observability` — a single process-wide singleton with
thread-safe counter bumps + a frozen snapshot type. The dashboard's
``/api/queues/metrics`` reads from here.
"""

from __future__ import annotations

import threading

from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    QueueMetricsEngineSelfSnapshot,
)


class _EngineMetrics:
    """Thread-safe counter bag — one instance per process."""

    __slots__ = (
        "_contention_detections",
        "_events_dropped",
        "_events_ignored",
        "_events_observed",
        "_lock",
        "_pressure_transitions",
        "_queues_evicted",
        "_recursion_skips",
        "_saturation_detections",
        "_tracked_queues",
        "_updates_emitted",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events_observed = 0
        self._events_ignored = 0
        self._events_dropped = 0
        self._updates_emitted = 0
        self._pressure_transitions = 0
        self._contention_detections = 0
        self._saturation_detections = 0
        self._tracked_queues = 0
        self._queues_evicted = 0
        self._recursion_skips = 0

    # ── bumps ─────────────────────────────────────────────────────────

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

    def record_pressure_transition(self) -> None:
        with self._lock:
            self._pressure_transitions += 1

    def record_contention_detected(self) -> None:
        with self._lock:
            self._contention_detections += 1

    def record_saturation_detected(self) -> None:
        with self._lock:
            self._saturation_detections += 1

    def record_queue_evicted(self) -> None:
        with self._lock:
            self._queues_evicted += 1

    def record_recursion_skip(self) -> None:
        with self._lock:
            self._recursion_skips += 1

    def set_tracked_queues(self, count: int) -> None:
        with self._lock:
            self._tracked_queues = count

    # ── snapshot / reset ──────────────────────────────────────────────

    def snapshot(self) -> QueueMetricsEngineSelfSnapshot:
        with self._lock:
            return QueueMetricsEngineSelfSnapshot(
                events_observed=self._events_observed,
                events_ignored=self._events_ignored,
                events_dropped=self._events_dropped,
                updates_emitted=self._updates_emitted,
                pressure_transitions=self._pressure_transitions,
                contention_detections=self._contention_detections,
                saturation_detections=self._saturation_detections,
                tracked_queues=self._tracked_queues,
                queues_evicted=self._queues_evicted,
                recursion_skips=self._recursion_skips,
            )

    def reset(self) -> None:
        with self._lock:
            self._events_observed = 0
            self._events_ignored = 0
            self._events_dropped = 0
            self._updates_emitted = 0
            self._pressure_transitions = 0
            self._contention_detections = 0
            self._saturation_detections = 0
            self._tracked_queues = 0
            self._queues_evicted = 0
            self._recursion_skips = 0


_default_metrics = _EngineMetrics()


def get_queue_metrics_engine_metrics() -> _EngineMetrics:
    return _default_metrics


def reset_queue_metrics_engine_metrics() -> None:
    _default_metrics.reset()
