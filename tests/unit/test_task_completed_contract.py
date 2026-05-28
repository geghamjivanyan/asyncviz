from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

import pytest_asyncio

from asyncviz.instrumentation.asyncio import AsyncioPatcher
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models import (
    TaskCompletedEvent,
    from_dict,
    to_dict,
)


@pytest_asyncio.fixture
async def bus_and_patcher() -> AsyncIterator[tuple[EventBus, AsyncioPatcher]]:
    bus = EventBus()
    await bus.start()
    patcher = AsyncioPatcher(bus)
    patcher.patch()
    try:
        yield bus, patcher
    finally:
        patcher.unpatch()
        await bus.stop()


# ── model shape ────────────────────────────────────────────────────────────


def test_task_completed_event_carries_full_terminal_envelope() -> None:
    event = TaskCompletedEvent(
        task_id="t1",
        task_name="worker",
        coroutine_name="my_coro",
        created_at=100.0,
        completed_at=100.5,
        duration_seconds=0.5,
    )
    assert event.event_type == "asyncio.task.completed"
    assert event.created_at == 100.0
    assert event.completed_at == 100.5
    assert event.duration_seconds == 0.5


def test_task_completed_event_roundtrips_through_serialization() -> None:
    original = TaskCompletedEvent(
        task_id="t1",
        task_name="worker",
        coroutine_name="my_coro",
        created_at=100.0,
        completed_at=100.5,
        duration_seconds=0.5,
    )
    rebuilt = from_dict(to_dict(original))
    assert isinstance(rebuilt, TaskCompletedEvent)
    assert rebuilt.created_at == 100.0
    assert rebuilt.completed_at == 100.5
    assert rebuilt.duration_seconds == 0.5
    assert rebuilt.task_name == "worker"


def test_task_completed_event_duration_is_non_negative_by_default() -> None:
    event = TaskCompletedEvent(task_id="t1")
    assert event.duration_seconds is None
    # explicit zero is fine
    explicit = TaskCompletedEvent(task_id="t1", duration_seconds=0.0)
    assert explicit.duration_seconds == 0.0


# ── instrumented timing ────────────────────────────────────────────────────


async def test_completion_emits_monotonic_duration(bus_and_patcher) -> None:
    bus, _patcher = bus_and_patcher
    received: list[TaskCompletedEvent] = []
    bus.subscribe(received.append, event_types={"asyncio.task.completed"})

    async def work() -> int:
        await asyncio.sleep(0.05)
        return 1

    before = time.time()
    task = asyncio.create_task(work(), name="t")
    await task
    after = time.time()
    await bus.join()

    assert len(received) == 1
    completed = received[0]

    # ``duration_seconds`` derived from monotonic clock; bounded by wall-clock
    # interval [before, after].
    assert completed.duration_seconds is not None
    assert 0.04 <= completed.duration_seconds <= (after - before) + 0.05

    # created_at + completed_at are wall-clock and fall within the same window.
    assert completed.created_at is not None
    assert completed.completed_at is not None
    assert before <= completed.created_at <= after
    assert before <= completed.completed_at <= after
    assert completed.created_at <= completed.completed_at


async def test_completion_duration_is_clamped_non_negative() -> None:
    """A pathological monotonic-jump must never produce a negative duration."""
    from asyncviz.instrumentation.asyncio.lifecycle import _publish_terminal_event

    # We can't actually move monotonic backwards; this verifies the explicit
    # max(0.0, …) clamp via a tiny artificial future ``started_at_monotonic``.
    bus = EventBus()
    await bus.start()
    received: list[TaskCompletedEvent] = []
    bus.subscribe(received.append, event_types={"asyncio.task.completed"})

    class FakeTask:
        def cancelled(self) -> bool:
            return False

        def exception(self) -> BaseException | None:
            return None

    _publish_terminal_event(
        FakeTask(),  # type: ignore[arg-type]
        task_id="t1",
        bus=bus,
        runtime_id=__import__("uuid").uuid4(),
        started_at=time.time(),
        started_at_monotonic_ns=time.monotonic_ns() + 10_000_000_000,  # future
        coroutine_name=None,
        task_name=None,
        cancellation_context=None,
    )
    await bus.join()
    await bus.stop()

    assert len(received) == 1
    assert received[0].duration_seconds == 0.0


# ── exactly-once + duplicate suppression ──────────────────────────────────


async def test_completion_fires_exactly_once(bus_and_patcher) -> None:
    bus, _patcher = bus_and_patcher
    received: list = []
    bus.subscribe(
        received.append,
        event_types={
            "asyncio.task.completed",
            "asyncio.task.failed",
            "asyncio.task.cancelled",
        },
    )

    async def work() -> int:
        return 1

    tasks = [asyncio.create_task(work()) for _ in range(100)]
    await asyncio.gather(*tasks)
    await bus.join()

    assert len(received) == 100
    # Each task_id appears exactly once across all terminal events.
    by_task = {ev.task_id for ev in received}
    assert len(by_task) == 100


# ── successful completion never co-emits failed/cancelled ─────────────────


async def test_successful_completion_never_emits_failed(bus_and_patcher) -> None:
    bus, _patcher = bus_and_patcher
    received: list = []
    bus.subscribe(
        received.append,
        event_types={
            "asyncio.task.completed",
            "asyncio.task.failed",
            "asyncio.task.cancelled",
        },
    )

    async def work() -> int:
        return 42

    task = asyncio.create_task(work())
    assert await task == 42
    await bus.join()

    event_types = [ev.event_type for ev in received]
    assert event_types == ["asyncio.task.completed"]
