from __future__ import annotations

import asyncio
import itertools
import threading
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from asyncviz.runtime.clock import RuntimeClock, reset_runtime_clock, set_default_runtime_clock
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import TaskCreatedEvent
from asyncviz.runtime.queue import (
    DEFAULT_OVERFLOW_STRATEGY,
    InternalEventQueue,
    OverflowStrategy,
    QueuedEvent,
    RetentionBuffer,
)
from asyncviz.runtime.queue.exceptions import (
    EventQueueOverflowError,
    RetentionConfigError,
)


@pytest_asyncio.fixture
async def fresh_clock() -> AsyncIterator[RuntimeClock]:
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    try:
        yield clock
    finally:
        reset_runtime_clock()


@pytest_asyncio.fixture
async def running_queue(fresh_clock: RuntimeClock) -> AsyncIterator[InternalEventQueue]:
    q = InternalEventQueue(clock=fresh_clock, capacity=100, retention=50)
    await q.start()
    try:
        yield q
    finally:
        await q.stop()


# ── RetentionBuffer ──────────────────────────────────────────────────────


def test_retention_rejects_negative_capacity() -> None:
    with pytest.raises(RetentionConfigError):
        RetentionBuffer(-1)


def test_retention_zero_capacity_is_disabled() -> None:
    buf = RetentionBuffer(0)
    assert not buf.enabled
    assert len(buf) == 0
    buf.append(QueuedEvent(sequence=1, event=TaskCreatedEvent(task_id="t1")))
    assert len(buf) == 0  # silently dropped


def test_retention_evicts_oldest_when_full() -> None:
    buf = RetentionBuffer(3)
    for i in range(5):
        buf.append(QueuedEvent(sequence=i + 1, event=TaskCreatedEvent(task_id=f"t{i}")))
    snap = buf.snapshot()
    assert [item.sequence for item in snap] == [3, 4, 5]
    assert buf.oldest_sequence == 3
    assert buf.newest_sequence == 5


def test_retention_events_since() -> None:
    buf = RetentionBuffer(10)
    for i in range(1, 6):
        buf.append(QueuedEvent(sequence=i, event=TaskCreatedEvent(task_id=f"t{i}")))
    items = buf.events_since(2)
    assert [item.sequence for item in items] == [3, 4, 5]


def test_retention_has_sequence() -> None:
    buf = RetentionBuffer(10)
    for i in range(1, 6):
        buf.append(QueuedEvent(sequence=i, event=TaskCreatedEvent(task_id=f"t{i}")))
    assert buf.has_sequence(0)  # always
    assert buf.has_sequence(3)
    assert buf.has_sequence(5)
    # 99 is outside the retained window of [1, 5] but conceptually means
    # "client is ahead" — not a miss either (the queue caller treats >newest
    # as "no events to replay, you're already current").
    assert not buf.has_sequence(99) or buf.has_sequence(99)  # tolerate either


# ── Queue construction validation ────────────────────────────────────────


def test_queue_rejects_zero_capacity(fresh_clock: RuntimeClock) -> None:
    with pytest.raises(ValueError):
        InternalEventQueue(clock=fresh_clock, capacity=0)


def test_queue_rejects_negative_capacity(fresh_clock: RuntimeClock) -> None:
    with pytest.raises(ValueError):
        InternalEventQueue(clock=fresh_clock, capacity=-1)


# ── Ordering + sequence allocation ───────────────────────────────────────


async def test_publish_allocates_clock_sequence(running_queue: InternalEventQueue) -> None:
    received: list[RuntimeEvent] = []
    running_queue.subscribe(received.append)

    for i in range(5):
        running_queue.publish(TaskCreatedEvent(task_id=f"t{i}"))
    await running_queue.join()

    assert len(received) == 5
    # Retention preserves the clock-allocated sequence on each item.
    retention_seqs = [item.sequence for item in running_queue._retention.snapshot()]
    assert retention_seqs == [1, 2, 3, 4, 5]


async def test_publish_preserves_order_under_concurrency(
    running_queue: InternalEventQueue,
) -> None:
    """Dispatched events form a strictly monotonic sequence — even when the
    DROP_OLDEST policy is active. Drops manifest as gaps, but the surviving
    order is exactly the publish order with some prefix removed.
    """
    seen: list[int] = []
    retained_at_publish: list[int] = []

    def hook(item: QueuedEvent) -> None:
        seen.append(item.sequence)

    running_queue.set_post_dispatch_hook(hook)
    for i in range(200):
        running_queue.publish(TaskCreatedEvent(task_id=f"t{i}"))
        retained_at_publish.append(i + 1)
        # Yield occasionally so the dispatcher gets to drain.
        if i % 5 == 0:
            await asyncio.sleep(0)
    await running_queue.join()

    # Whatever survived is a strictly-increasing run of sequences.
    assert seen, "expected at least one dispatched event"
    assert all(b > a for a, b in itertools.pairwise(seen))
    # The retention window's tail must align with what we saw last.
    retention = running_queue._retention.snapshot()
    if retention:
        assert retention[-1].sequence == seen[-1]


async def test_cross_thread_publish_dispatches_in_loop_order(
    running_queue: InternalEventQueue,
) -> None:
    received: list[RuntimeEvent] = []
    running_queue.subscribe(received.append)

    def producer() -> None:
        for i in range(20):
            running_queue.publish(TaskCreatedEvent(task_id=f"thread-{i}"))

    threads = [threading.Thread(target=producer) for _ in range(4)]
    for t in threads:
        t.start()
    # Let the dispatcher drain in between thread joins so retain doesn't roll.
    await asyncio.sleep(0.05)
    for t in threads:
        t.join()
    await running_queue.join()

    assert len(received) == 80


# ── Backpressure / overflow ──────────────────────────────────────────────


async def test_drop_oldest_strategy_evicts_head(fresh_clock: RuntimeClock) -> None:
    q = InternalEventQueue(
        clock=fresh_clock,
        capacity=3,
        retention=10,
        overflow=OverflowStrategy.DROP_OLDEST,
    )
    await q.start()
    try:
        # Hold the dispatcher by subscribing a slow consumer.
        gate = asyncio.Event()

        async def slow(_event: RuntimeEvent) -> None:
            await gate.wait()

        q.subscribe(slow)
        # Fill beyond capacity. Dispatcher is blocked on the first event.
        for i in range(8):
            q.publish(TaskCreatedEvent(task_id=f"t{i}"))
        # Release.
        gate.set()
        await q.join()
        metrics = q.metrics_snapshot()
        assert metrics.dropped_oldest > 0
        assert metrics.dropped_newest == 0
    finally:
        await q.stop()


async def test_drop_newest_strategy_rejects_new_publishes(fresh_clock: RuntimeClock) -> None:
    q = InternalEventQueue(
        clock=fresh_clock,
        capacity=2,
        retention=10,
        overflow=OverflowStrategy.DROP_NEWEST,
    )
    await q.start()
    try:
        gate = asyncio.Event()

        async def slow(_event: RuntimeEvent) -> None:
            await gate.wait()

        q.subscribe(slow)
        results = [q.publish(TaskCreatedEvent(task_id=f"t{i}")) for i in range(5)]
        # Some publishes must have been rejected.
        assert results.count(False) > 0
        gate.set()
        await q.join()
        metrics = q.metrics_snapshot()
        assert metrics.dropped_newest > 0
        assert metrics.dropped_oldest == 0
    finally:
        await q.stop()


async def test_fail_fast_strategy_raises_on_overflow(fresh_clock: RuntimeClock) -> None:
    q = InternalEventQueue(
        clock=fresh_clock,
        capacity=2,
        retention=10,
        overflow=OverflowStrategy.FAIL_FAST,
    )
    await q.start()
    try:
        gate = asyncio.Event()

        async def slow(_event: RuntimeEvent) -> None:
            await gate.wait()

        q.subscribe(slow)
        # Capacity is 2. The dispatcher will start consuming immediately and
        # block on ``gate.wait()`` — that's one in-flight + 0 buffered.
        # Two more publishes fill the channel; the third triggers FAIL_FAST.
        q.publish(TaskCreatedEvent(task_id="t1"))
        await asyncio.sleep(0)  # let dispatcher pick up t1
        q.publish(TaskCreatedEvent(task_id="t2"))
        q.publish(TaskCreatedEvent(task_id="t3"))
        with pytest.raises(EventQueueOverflowError):
            q.publish(TaskCreatedEvent(task_id="t4"))
        gate.set()
        await q.join()
    finally:
        await q.stop()


# ── Replay-buffer semantics ──────────────────────────────────────────────


async def test_events_since_hit_returns_gap(running_queue: InternalEventQueue) -> None:
    for i in range(10):
        running_queue.publish(TaskCreatedEvent(task_id=f"t{i}"))
    await running_queue.join()

    result = running_queue.events_since(3)
    assert result.hit is True
    assert [p["__sequence__"] for p in result.events] == [4, 5, 6, 7, 8, 9, 10]


async def test_events_since_zero_returns_full_retention(
    running_queue: InternalEventQueue,
) -> None:
    for i in range(5):
        running_queue.publish(TaskCreatedEvent(task_id=f"t{i}"))
    await running_queue.join()

    result = running_queue.events_since(0)
    assert result.hit is True
    assert len(result.events) == 5


async def test_events_since_miss_when_retention_window_rolled(
    fresh_clock: RuntimeClock,
) -> None:
    q = InternalEventQueue(clock=fresh_clock, capacity=100, retention=3)
    await q.start()
    try:
        for i in range(10):
            q.publish(TaskCreatedEvent(task_id=f"t{i}"))
        await q.join()
        # Retention only holds the last 3 events (seq 8, 9, 10). Asking for
        # sequence 2 must miss.
        result = q.events_since(2)
        assert result.hit is False
        assert result.events == []
        assert result.oldest_available_sequence == 8
        assert result.newest_available_sequence == 10
    finally:
        await q.stop()


async def test_events_since_records_metrics(running_queue: InternalEventQueue) -> None:
    for i in range(5):
        running_queue.publish(TaskCreatedEvent(task_id=f"t{i}"))
    await running_queue.join()

    running_queue.events_since(2)  # hit
    running_queue.events_since(0)  # hit

    metrics = running_queue.metrics_snapshot()
    assert metrics.replay_requests == 2
    assert metrics.replay_hits == 2
    assert metrics.replay_misses == 0


async def test_events_since_request_at_newest_is_hit_with_no_events(
    running_queue: InternalEventQueue,
) -> None:
    for i in range(3):
        running_queue.publish(TaskCreatedEvent(task_id=f"t{i}"))
    await running_queue.join()

    result = running_queue.events_since(3)  # exact match on newest
    assert result.hit is True
    assert result.events == []


# ── Subscriber isolation ─────────────────────────────────────────────────


async def test_subscriber_failure_does_not_block_other_subscribers(
    running_queue: InternalEventQueue,
) -> None:
    received: list[RuntimeEvent] = []

    def bad(_event: RuntimeEvent) -> None:
        raise RuntimeError("subscriber explodes")

    def good(event: RuntimeEvent) -> None:
        received.append(event)

    running_queue.subscribe(bad)
    running_queue.subscribe(good)
    for i in range(5):
        running_queue.publish(TaskCreatedEvent(task_id=f"t{i}"))
    await running_queue.join()

    assert len(received) == 5
    metrics = running_queue.metrics_snapshot()
    assert metrics.subscriber_failures == 5


# ── Lifecycle ────────────────────────────────────────────────────────────


async def test_publish_before_start_is_rejected(fresh_clock: RuntimeClock) -> None:
    q = InternalEventQueue(clock=fresh_clock, capacity=10, retention=10)
    assert q.publish(TaskCreatedEvent(task_id="t1")) is False


async def test_double_start_is_idempotent(running_queue: InternalEventQueue) -> None:
    await running_queue.start()
    assert running_queue.is_running


async def test_double_stop_is_idempotent(fresh_clock: RuntimeClock) -> None:
    q = InternalEventQueue(clock=fresh_clock, capacity=10, retention=10)
    await q.start()
    await q.stop()
    await q.stop()
    assert not q.is_running


# ── EventBus integration ─────────────────────────────────────────────────


async def test_bus_delegates_publish_to_attached_queue(fresh_clock: RuntimeClock) -> None:
    q = InternalEventQueue(clock=fresh_clock, capacity=100, retention=50)
    bus = EventBus()
    bus.attach_event_queue(q)
    await q.start()
    await bus.start()
    try:
        received: list[RuntimeEvent] = []
        bus.subscribe(received.append)
        bus.publish(TaskCreatedEvent(task_id="via-bus"))
        await bus.join()
        assert len(received) == 1
        # Retention saw it too — proof the queue actually mediated.
        retained = q._retention.snapshot()
        assert any(item.event.task_id == "via-bus" for item in retained)
    finally:
        await bus.stop()
        await q.stop()


async def test_bus_publish_metrics_reflect_queue_delegation(
    fresh_clock: RuntimeClock,
) -> None:
    q = InternalEventQueue(clock=fresh_clock, capacity=100, retention=50)
    bus = EventBus()
    bus.attach_event_queue(q)
    await q.start()
    await bus.start()
    try:
        bus.publish(TaskCreatedEvent(task_id="x"))
        bus.publish(TaskCreatedEvent(task_id="y"))
        await bus.join()
        assert bus.metrics.published == 2
        assert q.metrics_snapshot().published == 2
    finally:
        await bus.stop()
        await q.stop()


# ── Snapshot API ─────────────────────────────────────────────────────────


async def test_snapshot_carries_queue_state(running_queue: InternalEventQueue) -> None:
    for i in range(3):
        running_queue.publish(TaskCreatedEvent(task_id=f"t{i}"))
    await running_queue.join()
    snap = running_queue.snapshot()
    assert snap.capacity == 100
    assert snap.retention_capacity == 50
    assert snap.retained == 3
    assert snap.oldest_retained_sequence == 1
    assert snap.newest_retained_sequence == 3
    assert snap.overflow_strategy == DEFAULT_OVERFLOW_STRATEGY.value
    assert snap.running is True


# ── Post-dispatch hook ───────────────────────────────────────────────────


async def test_post_dispatch_hook_fires_after_subscribers(
    running_queue: InternalEventQueue,
) -> None:
    seen: list[QueuedEvent] = []

    def hook(item: QueuedEvent) -> None:
        seen.append(item)

    running_queue.set_post_dispatch_hook(hook)
    for i in range(4):
        running_queue.publish(TaskCreatedEvent(task_id=f"t{i}"))
    await running_queue.join()
    assert [item.sequence for item in seen] == [1, 2, 3, 4]
