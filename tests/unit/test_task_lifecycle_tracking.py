from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

import pytest_asyncio

from asyncviz.instrumentation.asyncio import AsyncioPatcher
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
)
from asyncviz.runtime.events.models.enums import EventType, TaskState
from asyncviz.runtime.tasks import TaskMetadata, TaskRegistry


@pytest_asyncio.fixture
async def wired() -> AsyncIterator[tuple[EventBus, AsyncioPatcher, TaskRegistry]]:
    bus = EventBus()
    await bus.start()
    registry = TaskRegistry()
    sub = bus.subscribe(
        registry.handle_event,
        event_types={
            EventType.TASK_CREATED,
            EventType.TASK_STARTED,
            EventType.TASK_WAITING,
            EventType.TASK_RESUMED,
            EventType.TASK_COMPLETED,
            EventType.TASK_CANCELLED,
            EventType.TASK_FAILED,
        },
    )
    patcher = AsyncioPatcher(bus)
    patcher.patch()
    try:
        yield bus, patcher, registry
    finally:
        patcher.unpatch()
        bus.unsubscribe(sub)
        await bus.stop()


async def test_completion_records_duration_and_state(wired) -> None:
    bus, _patcher, registry = wired

    async def work() -> int:
        await asyncio.sleep(0.01)
        return 42

    task = asyncio.create_task(work(), name="ok-task")
    result = await task
    await bus.join()

    assert result == 42
    snapshots = registry.snapshot_all_tasks()
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.state == TaskState.COMPLETED
    assert snap.task_name == "ok-task"
    assert snap.duration_seconds is not None
    assert snap.duration_seconds >= 0.01
    assert snap.completed_at is not None
    assert snap.exception_type is None


async def test_cancellation_records_terminal_state(wired) -> None:
    bus, _patcher, registry = wired

    async def hang() -> None:
        await asyncio.sleep(60)

    task = asyncio.create_task(hang(), name="hang-task")
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    await bus.join()

    snap = registry.snapshot_task(_only_task_id(registry))
    assert snap is not None
    assert snap.state == TaskState.CANCELLED
    assert snap.task_name == "hang-task"


async def test_failure_records_exception_metadata(wired) -> None:
    bus, _patcher, registry = wired

    async def boom() -> None:
        raise RuntimeError("kaboom!")

    task = asyncio.create_task(boom(), name="failing-task")
    with contextlib.suppress(RuntimeError):
        await task
    await bus.join()

    snap = registry.snapshot_task(_only_task_id(registry))
    assert snap is not None
    assert snap.state == TaskState.FAILED
    assert snap.exception_type == "RuntimeError"
    assert snap.exception_message == "kaboom!"
    assert snap.duration_seconds is not None


async def test_terminal_event_carries_task_name(wired) -> None:
    bus, _patcher, _registry = wired
    received: list = []
    bus.subscribe(
        received.append,
        event_types={
            EventType.TASK_CREATED,
            EventType.TASK_COMPLETED,
        },
    )

    async def work() -> None:
        return None

    task = asyncio.create_task(work(), name="enriched")
    await task
    await bus.join()

    created = [e for e in received if isinstance(e, TaskCreatedEvent)]
    completed = [e for e in received if isinstance(e, TaskCompletedEvent)]
    assert len(created) == 1
    assert len(completed) == 1
    assert completed[0].task_name == "enriched"
    assert completed[0].coroutine_name == created[0].coroutine_name
    assert completed[0].duration_seconds is not None


async def test_duplicate_terminal_event_is_silently_dropped() -> None:
    """If a terminal event is somehow published twice, the registry stays sane."""
    registry = TaskRegistry()
    registry.register("t1", metadata=TaskMetadata(coroutine_name="x"))

    # First terminal — accepted
    registry.handle_event(TaskCompletedEvent(task_id="t1", duration_seconds=0.1))
    # Second terminal — silently rejected (logged at debug)
    registry.handle_event(TaskCompletedEvent(task_id="t1", duration_seconds=0.2))

    snap = registry.snapshot_task("t1")
    assert snap is not None
    assert snap.state == TaskState.COMPLETED
    assert snap.duration_seconds == 0.1  # first event wins

    metrics = registry.metrics_snapshot()
    assert metrics.completed_tasks == 1
    assert metrics.rejected_transitions == 1


async def test_average_duration_reflects_completed_tasks() -> None:
    registry = TaskRegistry()

    # Three completions with known durations.
    for i, dur in enumerate([0.1, 0.2, 0.3], start=1):
        tid = f"t{i}"
        registry.register(tid)
        registry.handle_event(TaskCompletedEvent(task_id=tid, duration_seconds=dur))

    metrics = registry.metrics_snapshot()
    assert metrics.completed_tasks == 3
    assert metrics.average_duration_seconds is not None
    assert abs(metrics.average_duration_seconds - 0.2) < 1e-9


async def test_failures_and_cancellations_count_into_average() -> None:
    registry = TaskRegistry()

    registry.register("ok")
    registry.handle_event(TaskCompletedEvent(task_id="ok", duration_seconds=0.5))

    registry.register("bad")
    registry.handle_event(TaskFailedEvent(task_id="bad", duration_seconds=1.0, exception_type="X"))

    registry.register("gone")
    registry.handle_event(TaskCancelledEvent(task_id="gone", duration_seconds=0.5))

    metrics = registry.metrics_snapshot()
    assert metrics.terminal_tasks == 3
    # (0.5 + 1.0 + 0.5) / 3
    assert metrics.average_duration_seconds is not None
    assert abs(metrics.average_duration_seconds - (2.0 / 3.0)) < 1e-9


async def test_concurrent_terminations_produce_correct_counts(wired) -> None:
    bus, _patcher, registry = wired

    async def child(i: int) -> int:
        if i % 3 == 0:
            raise ValueError(f"three-mult: {i}")
        return i

    tasks = [asyncio.create_task(child(i), name=f"c{i}") for i in range(60)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    await bus.join()

    expected_failed = sum(1 for r in results if isinstance(r, ValueError))
    expected_completed = sum(1 for r in results if not isinstance(r, BaseException))

    metrics = registry.metrics_snapshot()
    assert metrics.total_tasks == 60
    assert metrics.completed_tasks == expected_completed
    assert metrics.failed_tasks == expected_failed
    assert metrics.active_tasks == 0


def _only_task_id(registry: TaskRegistry) -> str:
    snapshots = registry.snapshot_all_tasks()
    assert len(snapshots) == 1
    return snapshots[0].task_id
