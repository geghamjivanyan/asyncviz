"""Per-queue contention tracker.

Reads ``blocked_putters`` / ``blocked_getters`` from the snapshot dict
that every queue event carries (populated by
:func:`asyncviz.instrumentation.queue.queue_state.snapshot_queue`) and
maintains both *instantaneous* and *lifetime* counters.

Edge detection — was-zero → now-positive transitions — drives the
contention-detected event in the engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    QueueContentionSnapshot,
)


@dataclass(slots=True)
class ContentionTracker:
    blocked_producers: int = 0
    blocked_consumers: int = 0
    blocked_put_count: int = 0
    blocked_get_count: int = 0
    full_wait_count: int = 0
    empty_wait_count: int = 0
    cancelled_count: int = 0
    peak_blocked_producers: int = 0
    peak_blocked_consumers: int = 0

    def update_blocked(self, *, producers: int, consumers: int) -> None:
        if producers < 0:
            producers = 0
        if consumers < 0:
            consumers = 0
        self.blocked_producers = producers
        self.blocked_consumers = consumers
        if producers > self.peak_blocked_producers:
            self.peak_blocked_producers = producers
        if consumers > self.peak_blocked_consumers:
            self.peak_blocked_consumers = consumers

    def record_blocked_put(self) -> None:
        self.blocked_put_count += 1

    def record_blocked_get(self) -> None:
        self.blocked_get_count += 1

    def record_full_wait(self) -> None:
        self.full_wait_count += 1

    def record_empty_wait(self) -> None:
        self.empty_wait_count += 1

    def record_cancelled(self) -> None:
        self.cancelled_count += 1

    def snapshot(self) -> QueueContentionSnapshot:
        return QueueContentionSnapshot(
            blocked_producers=self.blocked_producers,
            blocked_consumers=self.blocked_consumers,
            blocked_put_count=self.blocked_put_count,
            blocked_get_count=self.blocked_get_count,
            full_wait_count=self.full_wait_count,
            empty_wait_count=self.empty_wait_count,
            cancelled_count=self.cancelled_count,
            peak_blocked_producers=self.peak_blocked_producers,
            peak_blocked_consumers=self.peak_blocked_consumers,
        )

    def reset(self) -> None:
        self.blocked_producers = 0
        self.blocked_consumers = 0
        self.blocked_put_count = 0
        self.blocked_get_count = 0
        self.full_wait_count = 0
        self.empty_wait_count = 0
        self.cancelled_count = 0
        self.peak_blocked_producers = 0
        self.peak_blocked_consumers = 0
