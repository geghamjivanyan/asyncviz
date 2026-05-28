"""Engine-level observability counters for gather instrumentation."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GatherMetricsSnapshot:
    gathers_instrumented: int
    gathers_finalized: int
    events_emitted: int
    events_dropped: int
    child_attached_events: int
    child_completed_events: int
    gathers_completed: int
    gathers_cancelled: int
    gathers_failed: int
    suppressed_calls: int
    recursion_skips: int


class _GatherMetrics:
    __slots__ = (
        "_child_attached",
        "_child_completed",
        "_events_dropped",
        "_events_emitted",
        "_finalized",
        "_gathers_cancelled",
        "_gathers_completed",
        "_gathers_failed",
        "_instrumented",
        "_lock",
        "_recursion_skips",
        "_suppressed_calls",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instrumented = 0
        self._finalized = 0
        self._events_emitted = 0
        self._events_dropped = 0
        self._child_attached = 0
        self._child_completed = 0
        self._gathers_completed = 0
        self._gathers_cancelled = 0
        self._gathers_failed = 0
        self._suppressed_calls = 0
        self._recursion_skips = 0

    def record_instrumented(self) -> None:
        with self._lock:
            self._instrumented += 1

    def record_finalized(self) -> None:
        with self._lock:
            self._finalized += 1

    def record_event(self) -> None:
        with self._lock:
            self._events_emitted += 1

    def record_dropped(self) -> None:
        with self._lock:
            self._events_dropped += 1

    def record_child_attached(self) -> None:
        with self._lock:
            self._child_attached += 1

    def record_child_completed(self) -> None:
        with self._lock:
            self._child_completed += 1

    def record_completed(self) -> None:
        with self._lock:
            self._gathers_completed += 1

    def record_cancelled(self) -> None:
        with self._lock:
            self._gathers_cancelled += 1

    def record_failed(self) -> None:
        with self._lock:
            self._gathers_failed += 1

    def record_suppressed(self) -> None:
        with self._lock:
            self._suppressed_calls += 1

    def record_recursion_skip(self) -> None:
        with self._lock:
            self._recursion_skips += 1

    def snapshot(self) -> GatherMetricsSnapshot:
        with self._lock:
            return GatherMetricsSnapshot(
                gathers_instrumented=self._instrumented,
                gathers_finalized=self._finalized,
                events_emitted=self._events_emitted,
                events_dropped=self._events_dropped,
                child_attached_events=self._child_attached,
                child_completed_events=self._child_completed,
                gathers_completed=self._gathers_completed,
                gathers_cancelled=self._gathers_cancelled,
                gathers_failed=self._gathers_failed,
                suppressed_calls=self._suppressed_calls,
                recursion_skips=self._recursion_skips,
            )

    def reset(self) -> None:
        with self._lock:
            self._instrumented = 0
            self._finalized = 0
            self._events_emitted = 0
            self._events_dropped = 0
            self._child_attached = 0
            self._child_completed = 0
            self._gathers_completed = 0
            self._gathers_cancelled = 0
            self._gathers_failed = 0
            self._suppressed_calls = 0
            self._recursion_skips = 0


_default_metrics = _GatherMetrics()


def get_gather_metrics() -> _GatherMetrics:
    return _default_metrics


def reset_gather_metrics() -> None:
    _default_metrics.reset()
