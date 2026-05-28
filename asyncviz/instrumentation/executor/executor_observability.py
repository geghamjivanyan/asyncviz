"""Engine-level observability counters for executor instrumentation."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutorMetricsSnapshot:
    executors_registered: int
    executors_finalized: int
    work_items_submitted: int
    work_items_started: int
    work_items_completed: int
    work_items_failed: int
    work_items_cancelled: int
    events_emitted: int
    events_dropped: int
    suppressed_calls: int
    recursion_skips: int


class _ExecutorMetrics:
    __slots__ = (
        "_events_dropped",
        "_events_emitted",
        "_executors_finalized",
        "_executors_registered",
        "_lock",
        "_recursion_skips",
        "_suppressed_calls",
        "_work_cancelled",
        "_work_completed",
        "_work_failed",
        "_work_started",
        "_work_submitted",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._executors_registered = 0
        self._executors_finalized = 0
        self._work_submitted = 0
        self._work_started = 0
        self._work_completed = 0
        self._work_failed = 0
        self._work_cancelled = 0
        self._events_emitted = 0
        self._events_dropped = 0
        self._suppressed_calls = 0
        self._recursion_skips = 0

    def record_executor_registered(self) -> None:
        with self._lock:
            self._executors_registered += 1

    def record_executor_finalized(self) -> None:
        with self._lock:
            self._executors_finalized += 1

    def record_work_submitted(self) -> None:
        with self._lock:
            self._work_submitted += 1

    def record_work_started(self) -> None:
        with self._lock:
            self._work_started += 1

    def record_work_completed(self) -> None:
        with self._lock:
            self._work_completed += 1

    def record_work_failed(self) -> None:
        with self._lock:
            self._work_failed += 1

    def record_work_cancelled(self) -> None:
        with self._lock:
            self._work_cancelled += 1

    def record_event(self) -> None:
        with self._lock:
            self._events_emitted += 1

    def record_dropped(self) -> None:
        with self._lock:
            self._events_dropped += 1

    def record_suppressed(self) -> None:
        with self._lock:
            self._suppressed_calls += 1

    def record_recursion_skip(self) -> None:
        with self._lock:
            self._recursion_skips += 1

    def snapshot(self) -> ExecutorMetricsSnapshot:
        with self._lock:
            return ExecutorMetricsSnapshot(
                executors_registered=self._executors_registered,
                executors_finalized=self._executors_finalized,
                work_items_submitted=self._work_submitted,
                work_items_started=self._work_started,
                work_items_completed=self._work_completed,
                work_items_failed=self._work_failed,
                work_items_cancelled=self._work_cancelled,
                events_emitted=self._events_emitted,
                events_dropped=self._events_dropped,
                suppressed_calls=self._suppressed_calls,
                recursion_skips=self._recursion_skips,
            )

    def reset(self) -> None:
        with self._lock:
            self._executors_registered = 0
            self._executors_finalized = 0
            self._work_submitted = 0
            self._work_started = 0
            self._work_completed = 0
            self._work_failed = 0
            self._work_cancelled = 0
            self._events_emitted = 0
            self._events_dropped = 0
            self._suppressed_calls = 0
            self._recursion_skips = 0


_default_metrics = _ExecutorMetrics()


def get_executor_metrics() -> _ExecutorMetrics:
    return _default_metrics


def reset_executor_metrics() -> None:
    _default_metrics.reset()
