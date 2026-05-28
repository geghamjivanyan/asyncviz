from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueueMetricsSnapshot:
    """Immutable point-in-time view of :class:`QueueMetrics`.

    All counters are monotonically increasing for the lifetime of the queue
    instance. ``depth`` and ``retained`` are gauges (instantaneous values).

    These names are part of the public protocol — coordinate with the
    TypeScript ``QueueMetricsSnapshot`` and the ``/api/runtime/queue`` route.
    """

    published: int
    dispatched: int
    dropped_overflow: int
    dropped_oldest: int
    dropped_newest: int
    fail_fast_rejections: int
    subscriber_failures: int
    replay_requests: int
    replay_hits: int
    replay_misses: int
    replay_events_emitted: int
    depth: int
    retained: int
    capacity: int
    retention_capacity: int


class QueueMetrics:
    """Mutable counters owned by :class:`InternalEventQueue`.

    Updates happen on the dashboard's event-loop thread for the dispatch
    side, and from arbitrary threads on the publish side. A single lock
    serializes all writes; reads via :meth:`snapshot` are atomic.
    """

    __slots__ = (
        "_dispatched",
        "_dropped_newest",
        "_dropped_oldest",
        "_dropped_overflow",
        "_fail_fast_rejections",
        "_lock",
        "_published",
        "_replay_events_emitted",
        "_replay_hits",
        "_replay_misses",
        "_replay_requests",
        "_subscriber_failures",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._published = 0
        self._dispatched = 0
        self._dropped_overflow = 0
        self._dropped_oldest = 0
        self._dropped_newest = 0
        self._fail_fast_rejections = 0
        self._subscriber_failures = 0
        self._replay_requests = 0
        self._replay_hits = 0
        self._replay_misses = 0
        self._replay_events_emitted = 0

    # ── publish-side accounting ──────────────────────────────────────────
    def record_published(self) -> None:
        with self._lock:
            self._published += 1

    def record_dropped_oldest(self) -> None:
        with self._lock:
            self._dropped_overflow += 1
            self._dropped_oldest += 1

    def record_dropped_newest(self) -> None:
        with self._lock:
            self._dropped_overflow += 1
            self._dropped_newest += 1

    def record_fail_fast(self) -> None:
        with self._lock:
            self._dropped_overflow += 1
            self._fail_fast_rejections += 1

    # ── dispatch-side accounting ─────────────────────────────────────────
    def record_dispatched(self) -> None:
        with self._lock:
            self._dispatched += 1

    def record_subscriber_failure(self) -> None:
        with self._lock:
            self._subscriber_failures += 1

    # ── replay-side accounting ───────────────────────────────────────────
    def record_replay_request(self) -> None:
        with self._lock:
            self._replay_requests += 1

    def record_replay_hit(self, emitted: int) -> None:
        with self._lock:
            self._replay_hits += 1
            self._replay_events_emitted += emitted

    def record_replay_miss(self) -> None:
        with self._lock:
            self._replay_misses += 1

    def snapshot(
        self,
        *,
        depth: int,
        retained: int,
        capacity: int,
        retention_capacity: int,
    ) -> QueueMetricsSnapshot:
        with self._lock:
            return QueueMetricsSnapshot(
                published=self._published,
                dispatched=self._dispatched,
                dropped_overflow=self._dropped_overflow,
                dropped_oldest=self._dropped_oldest,
                dropped_newest=self._dropped_newest,
                fail_fast_rejections=self._fail_fast_rejections,
                subscriber_failures=self._subscriber_failures,
                replay_requests=self._replay_requests,
                replay_hits=self._replay_hits,
                replay_misses=self._replay_misses,
                replay_events_emitted=self._replay_events_emitted,
                depth=depth,
                retained=retained,
                capacity=capacity,
                retention_capacity=retention_capacity,
            )
