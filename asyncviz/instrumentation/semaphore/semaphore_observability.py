"""Engine-level observability counters for semaphore instrumentation.

Process-wide singleton with thread-safe counter bumps + a frozen
snapshot type. The diagnostics endpoint reads from here.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SemaphoreMetricsSnapshot:
    semaphores_registered: int
    semaphores_finalized: int
    events_emitted: int
    events_dropped: int
    acquire_events: int
    release_events: int
    cancelled_waits: int
    contention_detections: int
    blocked_acquires: int
    recursion_skips: int


class _SemaphoreMetrics:
    __slots__ = (
        "_acquire_events",
        "_blocked_acquires",
        "_cancelled_waits",
        "_contention_detections",
        "_events_dropped",
        "_events_emitted",
        "_lock",
        "_recursion_skips",
        "_release_events",
        "_semaphores_finalized",
        "_semaphores_registered",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._semaphores_registered = 0
        self._semaphores_finalized = 0
        self._events_emitted = 0
        self._events_dropped = 0
        self._acquire_events = 0
        self._release_events = 0
        self._cancelled_waits = 0
        self._contention_detections = 0
        self._blocked_acquires = 0
        self._recursion_skips = 0

    def record_registered(self) -> None:
        with self._lock:
            self._semaphores_registered += 1

    def record_finalized(self) -> None:
        with self._lock:
            self._semaphores_finalized += 1

    def record_event(self) -> None:
        with self._lock:
            self._events_emitted += 1

    def record_dropped(self) -> None:
        with self._lock:
            self._events_dropped += 1

    def record_acquire(self, *, blocked: bool) -> None:
        with self._lock:
            self._acquire_events += 1
            if blocked:
                self._blocked_acquires += 1

    def record_release(self) -> None:
        with self._lock:
            self._release_events += 1

    def record_cancelled(self) -> None:
        with self._lock:
            self._cancelled_waits += 1

    def record_contention(self) -> None:
        with self._lock:
            self._contention_detections += 1

    def record_recursion_skip(self) -> None:
        with self._lock:
            self._recursion_skips += 1

    def snapshot(self) -> SemaphoreMetricsSnapshot:
        with self._lock:
            return SemaphoreMetricsSnapshot(
                semaphores_registered=self._semaphores_registered,
                semaphores_finalized=self._semaphores_finalized,
                events_emitted=self._events_emitted,
                events_dropped=self._events_dropped,
                acquire_events=self._acquire_events,
                release_events=self._release_events,
                cancelled_waits=self._cancelled_waits,
                contention_detections=self._contention_detections,
                blocked_acquires=self._blocked_acquires,
                recursion_skips=self._recursion_skips,
            )

    def reset(self) -> None:
        with self._lock:
            self._semaphores_registered = 0
            self._semaphores_finalized = 0
            self._events_emitted = 0
            self._events_dropped = 0
            self._acquire_events = 0
            self._release_events = 0
            self._cancelled_waits = 0
            self._contention_detections = 0
            self._blocked_acquires = 0
            self._recursion_skips = 0


_default_metrics = _SemaphoreMetrics()


def get_semaphore_metrics() -> _SemaphoreMetrics:
    return _default_metrics


def reset_semaphore_metrics() -> None:
    _default_metrics.reset()
