"""Process-wide counters for queue instrumentation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueueMetricsSnapshot:
    queues_registered: int
    queues_finalized: int
    events_emitted: int
    events_dropped: int
    put_events: int
    get_events: int
    blocked_puts: int
    blocked_gets: int
    full_waits: int
    empty_waits: int
    cancelled_waits: int
    task_done_events: int
    recursion_skips: int


class _QueueMetrics:
    def __init__(self) -> None:
        self._queues_registered = 0
        self._queues_finalized = 0
        self._events_emitted = 0
        self._events_dropped = 0
        self._put = 0
        self._get = 0
        self._blocked_puts = 0
        self._blocked_gets = 0
        self._full_waits = 0
        self._empty_waits = 0
        self._cancelled = 0
        self._task_done = 0
        self._recursion = 0

    def record_registered(self) -> None:
        self._queues_registered += 1

    def record_finalized(self) -> None:
        self._queues_finalized += 1

    def record_event(self) -> None:
        self._events_emitted += 1

    def record_dropped(self) -> None:
        self._events_dropped += 1

    def record_put(self, *, blocked: bool) -> None:
        self._put += 1
        if blocked:
            self._blocked_puts += 1

    def record_get(self, *, blocked: bool) -> None:
        self._get += 1
        if blocked:
            self._blocked_gets += 1

    def record_full_wait(self) -> None:
        self._full_waits += 1

    def record_empty_wait(self) -> None:
        self._empty_waits += 1

    def record_cancelled(self) -> None:
        self._cancelled += 1

    def record_task_done(self) -> None:
        self._task_done += 1

    def record_recursion_skip(self) -> None:
        self._recursion += 1

    def snapshot(self) -> QueueMetricsSnapshot:
        return QueueMetricsSnapshot(
            queues_registered=self._queues_registered,
            queues_finalized=self._queues_finalized,
            events_emitted=self._events_emitted,
            events_dropped=self._events_dropped,
            put_events=self._put,
            get_events=self._get,
            blocked_puts=self._blocked_puts,
            blocked_gets=self._blocked_gets,
            full_waits=self._full_waits,
            empty_waits=self._empty_waits,
            cancelled_waits=self._cancelled,
            task_done_events=self._task_done,
            recursion_skips=self._recursion,
        )

    def reset(self) -> None:
        self.__init__()


_instance = _QueueMetrics()


def get_queue_metrics() -> _QueueMetrics:
    return _instance


def reset_queue_metrics() -> None:
    _instance.reset()
