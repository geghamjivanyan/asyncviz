from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from asyncviz.runtime.events import (
    EventBus,
    EventBusNotRunningError,
    InvalidSubscriptionError,
    RuntimeEvent,
)


@pytest_asyncio.fixture
async def bus() -> AsyncIterator[EventBus]:
    bus = EventBus(maxsize=128)
    await bus.start()
    try:
        yield bus
    finally:
        await bus.stop()


async def test_publish_to_async_subscriber(bus: EventBus) -> None:
    received: list[RuntimeEvent] = []

    async def handler(event: RuntimeEvent) -> None:
        received.append(event)

    bus.subscribe(handler, event_types={"task.created"})
    assert bus.publish(RuntimeEvent.of("task.created", id=1)) is True
    await bus.join()

    assert len(received) == 1
    assert received[0].event_type == "task.created"
    assert received[0].payload == {"id": 1}


async def test_publish_to_sync_subscriber(bus: EventBus) -> None:
    received: list[str] = []

    def handler(event: RuntimeEvent) -> None:
        received.append(event.event_type)

    bus.subscribe(handler, event_types={"system.startup"})
    bus.publish(RuntimeEvent.of("system.startup"))
    await bus.join()

    assert received == ["system.startup"]


async def test_event_type_filtering(bus: EventBus) -> None:
    seen_a: list[RuntimeEvent] = []
    seen_b: list[RuntimeEvent] = []

    bus.subscribe(seen_a.append, event_types={"a"})
    bus.subscribe(seen_b.append, event_types={"b"})

    bus.publish(RuntimeEvent.of("a"))
    bus.publish(RuntimeEvent.of("b"))
    bus.publish(RuntimeEvent.of("c"))
    await bus.join()

    assert [e.event_type for e in seen_a] == ["a"]
    assert [e.event_type for e in seen_b] == ["b"]


async def test_wildcard_subscriber_receives_everything(bus: EventBus) -> None:
    seen: list[str] = []
    bus.subscribe(lambda e: seen.append(e.event_type), event_types=None)

    bus.publish(RuntimeEvent.of("a"))
    bus.publish(RuntimeEvent.of("b"))
    bus.publish(RuntimeEvent.of("c"))
    await bus.join()

    assert seen == ["a", "b", "c"]


async def test_multiple_subscribers_for_same_type(bus: EventBus) -> None:
    counts = [0, 0, 0]

    def make(idx: int):
        def handler(_event: RuntimeEvent) -> None:
            counts[idx] += 1

        return handler

    for i in range(3):
        bus.subscribe(make(i), event_types={"shared"})

    bus.publish(RuntimeEvent.of("shared"))
    bus.publish(RuntimeEvent.of("shared"))
    await bus.join()

    assert counts == [2, 2, 2]


async def test_unsubscribe_stops_delivery(bus: EventBus) -> None:
    received: list[RuntimeEvent] = []
    sub = bus.subscribe(received.append, event_types={"x"})

    bus.publish(RuntimeEvent.of("x"))
    await bus.join()
    assert len(received) == 1

    assert bus.unsubscribe(sub) is True
    bus.publish(RuntimeEvent.of("x"))
    await bus.join()
    assert len(received) == 1  # no new delivery

    # Repeated unsubscribe is a safe no-op.
    assert bus.unsubscribe(sub) is False


async def test_subscriber_failure_is_isolated(bus: EventBus) -> None:
    survived: list[RuntimeEvent] = []

    def angry(_event: RuntimeEvent) -> None:
        raise RuntimeError("boom")

    bus.subscribe(angry, event_types={"shared"})
    bus.subscribe(survived.append, event_types={"shared"})

    bus.publish(RuntimeEvent.of("shared"))
    bus.publish(RuntimeEvent.of("shared"))
    await bus.join()

    assert len(survived) == 2
    assert bus.metrics.subscriber_failures == 2


async def test_metrics_snapshot(bus: EventBus) -> None:
    bus.subscribe(lambda _e: None, event_types={"a"})
    bus.publish(RuntimeEvent.of("a"))
    bus.publish(RuntimeEvent.of("a"))
    await bus.join()

    snap = bus.metrics_snapshot()
    assert snap.published == 2
    assert snap.dispatched == 2
    assert snap.dropped == 0
    assert snap.subscriber_count == 1
    assert snap.queue_size == 0


async def test_drops_when_queue_full() -> None:
    bus = EventBus(maxsize=2)
    await bus.start()
    try:
        gate = asyncio.Event()

        async def slow(_event: RuntimeEvent) -> None:
            await gate.wait()

        bus.subscribe(slow, event_types={"x"})

        # First publish enters dispatcher; the rest queue up to maxsize.
        for _ in range(10):
            bus.publish(RuntimeEvent.of("x"))

        snap = bus.metrics_snapshot()
        assert snap.dropped > 0
        gate.set()
    finally:
        await bus.stop()


async def test_publish_after_stop_returns_false() -> None:
    bus = EventBus(maxsize=8)
    await bus.start()
    await bus.stop()
    assert bus.publish(RuntimeEvent.of("x")) is False
    assert bus.metrics.dropped >= 1


async def test_start_is_idempotent() -> None:
    bus = EventBus()
    await bus.start()
    first_task = bus._dispatcher_task
    await bus.start()
    assert bus._dispatcher_task is first_task
    await bus.stop()


async def test_stop_is_idempotent() -> None:
    bus = EventBus()
    await bus.start()
    await bus.stop()
    await bus.stop()
    assert bus.is_running is False


async def test_invalid_subscription_rejected(bus: EventBus) -> None:
    with pytest.raises(InvalidSubscriptionError):
        bus.subscribe("not a callable")  # type: ignore[arg-type]
    with pytest.raises(InvalidSubscriptionError):
        bus.subscribe(lambda _e: None, event_types={""})


async def test_join_on_stopped_bus_raises() -> None:
    bus = EventBus()
    with pytest.raises(EventBusNotRunningError):
        await bus.join()


async def test_cross_thread_publish() -> None:
    bus = EventBus(maxsize=1024)
    await bus.start()
    try:
        received: list[RuntimeEvent] = []
        bus.subscribe(received.append, event_types={"thread"})

        def worker() -> None:
            for i in range(50):
                bus.publish(RuntimeEvent.of("thread", i=i))

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(4)]
        for t in threads:
            t.start()
        # Yield to the loop while producer threads run so the dispatcher can
        # drain in parallel with new arrivals via call_soon_threadsafe.
        while any(t.is_alive() for t in threads):  # noqa: ASYNC110
            await asyncio.sleep(0.001)
        for t in threads:
            t.join()

        for _ in range(50):
            await asyncio.sleep(0)
            if len(received) == 200:
                break
        await bus.join()

        assert len(received) == 200
        assert bus.metrics.dropped == 0
        assert bus.metrics.published == 200
    finally:
        await bus.stop()


async def test_async_and_sync_subscribers_run_in_parallel(bus: EventBus) -> None:
    order: list[str] = []
    started = asyncio.Event()

    async def slow_async(_event: RuntimeEvent) -> None:
        started.set()
        await asyncio.sleep(0.01)
        order.append("async-done")

    def fast_sync(_event: RuntimeEvent) -> None:
        order.append("sync-done")

    bus.subscribe(slow_async, event_types={"x"})
    bus.subscribe(fast_sync, event_types={"x"})
    bus.publish(RuntimeEvent.of("x"))

    await bus.join()
    assert "async-done" in order
    assert "sync-done" in order
    # Sync handler runs synchronously inside the gather batch — it completes
    # before the async one finishes its sleep.
    assert order.index("sync-done") < order.index("async-done")
