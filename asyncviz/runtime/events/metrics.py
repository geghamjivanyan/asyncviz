from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EventBusMetricsSnapshot:
    published: int
    dispatched: int
    dropped: int
    subscriber_failures: int
    subscriber_count: int
    queue_size: int


@dataclass(slots=True)
class EventBusMetrics:
    """Lightweight counters maintained by the bus. Read via :meth:`snapshot`.

    All counters are mutated only from the bus's event loop thread, so we
    don't need locks. ``queue_size`` is queried live via ``Queue.qsize`` —
    not stored.
    """

    published: int = 0
    dispatched: int = 0
    dropped: int = 0
    subscriber_failures: int = 0

    def snapshot(self, *, subscriber_count: int, queue_size: int) -> EventBusMetricsSnapshot:
        return EventBusMetricsSnapshot(
            published=self.published,
            dispatched=self.dispatched,
            dropped=self.dropped,
            subscriber_failures=self.subscriber_failures,
            subscriber_count=subscriber_count,
            queue_size=queue_size,
        )
