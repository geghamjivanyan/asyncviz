"""Per-queue producer / consumer throughput counters + rate meters.

Reuses :class:`asyncviz.runtime.metrics.rates.RateMeter` so the rate
semantics match the rest of the runtime — including replay-deterministic
windowing on event monotonic time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    QueueThroughputSnapshot,
)
from asyncviz.runtime.metrics.rates import RateMeter


@dataclass(slots=True)
class ThroughputCounters:
    """Lifetime monotonic counters + sliding-window put/get rates."""

    window_seconds: int = 30
    put_count: int = 0
    get_count: int = 0
    nowait_put_count: int = 0
    nowait_get_count: int = 0
    task_done_count: int = 0
    cancelled_count: int = 0

    put_rate: RateMeter = field(init=False)
    get_rate: RateMeter = field(init=False)

    def __post_init__(self) -> None:
        self.put_rate = RateMeter(window_seconds=self.window_seconds)
        self.get_rate = RateMeter(window_seconds=self.window_seconds)

    def record_put(self, *, monotonic_seconds: float, nowait: bool) -> None:
        self.put_count += 1
        if nowait:
            self.nowait_put_count += 1
        self.put_rate.observe(monotonic_seconds=monotonic_seconds)

    def record_get(self, *, monotonic_seconds: float, nowait: bool) -> None:
        self.get_count += 1
        if nowait:
            self.nowait_get_count += 1
        self.get_rate.observe(monotonic_seconds=monotonic_seconds)

    def record_task_done(self) -> None:
        self.task_done_count += 1

    def record_cancelled(self) -> None:
        self.cancelled_count += 1

    def snapshot(self, *, monotonic_seconds: float | None = None) -> QueueThroughputSnapshot:
        put_rate = self.put_rate.snapshot(monotonic_seconds=monotonic_seconds).rate_per_second
        get_rate = self.get_rate.snapshot(monotonic_seconds=monotonic_seconds).rate_per_second
        return QueueThroughputSnapshot(
            put_count=self.put_count,
            get_count=self.get_count,
            put_rate=put_rate,
            get_rate=get_rate,
            producer_consumer_delta=self.put_count - self.get_count,
            task_done_count=self.task_done_count,
            nowait_put_count=self.nowait_put_count,
            nowait_get_count=self.nowait_get_count,
            cancelled_count=self.cancelled_count,
        )

    def reset(self) -> None:
        self.put_count = 0
        self.get_count = 0
        self.nowait_put_count = 0
        self.nowait_get_count = 0
        self.task_done_count = 0
        self.cancelled_count = 0
        self.put_rate.reset()
        self.get_rate.reset()
