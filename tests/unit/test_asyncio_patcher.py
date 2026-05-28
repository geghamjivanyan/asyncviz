from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.asyncio import AsyncioPatcher
from asyncviz.instrumentation.asyncio.metadata import (
    extract_coroutine_name,
    extract_task_name,
)
from asyncviz.runtime.events import (
    EventBus,
    RuntimeEvent,
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
)


@pytest_asyncio.fixture
async def bus_and_patcher() -> AsyncIterator[tuple[EventBus, AsyncioPatcher]]:
    bus = EventBus()
    await bus.start()
    patcher = AsyncioPatcher(bus)
    try:
        yield bus, patcher
    finally:
        if patcher.is_patched:
            patcher.unpatch()
        await bus.stop()


# ── metadata extraction ────────────────────────────────────────────────────


async def _worker() -> int:
    return 42


async def test_extract_coroutine_name_returns_qualname() -> None:
    coro = _worker()
    try:
        name = extract_coroutine_name(coro)
        assert name is not None
        assert "_worker" in name
    finally:
        coro.close()


async def test_extract_task_name_returns_get_name(bus_and_patcher) -> None:
    _bus, patcher = bus_and_patcher
    patcher.patch()
    task = asyncio.create_task(_worker(), name="custom-name")
    try:
        assert extract_task_name(task) == "custom-name"
    finally:
        await task


# ── patch / unpatch ────────────────────────────────────────────────────────


async def test_patch_replaces_create_task(bus_and_patcher) -> None:
    _bus, patcher = bus_and_patcher
    original = asyncio.create_task
    patcher.patch()
    assert asyncio.create_task is not original
    assert patcher.is_patched

    patcher.unpatch()
    assert asyncio.create_task is original
    assert not patcher.is_patched


async def test_repeated_patch_is_idempotent(bus_and_patcher) -> None:
    _bus, patcher = bus_and_patcher
    patcher.patch()
    wrapped = asyncio.create_task
    patcher.patch()
    patcher.patch()
    assert asyncio.create_task is wrapped


async def test_repeated_unpatch_is_safe(bus_and_patcher) -> None:
    _bus, patcher = bus_and_patcher
    patcher.unpatch()
    patcher.unpatch()
    assert not patcher.is_patched


# ── semantic preservation ──────────────────────────────────────────────────


async def test_task_result_is_preserved(bus_and_patcher) -> None:
    _bus, patcher = bus_and_patcher
    patcher.patch()
    task = asyncio.create_task(_worker())
    assert await task == 42


async def test_task_name_is_preserved(bus_and_patcher) -> None:
    _bus, patcher = bus_and_patcher
    patcher.patch()
    task = asyncio.create_task(_worker(), name="my-task")
    try:
        assert task.get_name() == "my-task"
    finally:
        await task


async def test_task_exception_propagates(bus_and_patcher) -> None:
    _bus, patcher = bus_and_patcher
    patcher.patch()

    async def boom() -> None:
        raise ValueError("kaboom")

    task = asyncio.create_task(boom())
    with pytest.raises(ValueError, match="kaboom"):
        await task


async def test_task_cancellation_preserved(bus_and_patcher) -> None:
    _bus, patcher = bus_and_patcher
    patcher.patch()

    async def slow() -> None:
        await asyncio.sleep(60)

    task = asyncio.create_task(slow())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


# ── event emission ─────────────────────────────────────────────────────────


async def test_task_created_event_is_published(bus_and_patcher) -> None:
    bus, patcher = bus_and_patcher
    received: list[RuntimeEvent] = []
    bus.subscribe(received.append, event_types={"asyncio.task.created"})
    patcher.patch()

    task = asyncio.create_task(_worker(), name="emit-me")
    await task
    await bus.join()

    created = [e for e in received if isinstance(e, TaskCreatedEvent)]
    assert len(created) == 1
    assert created[0].task_name == "emit-me"
    assert created[0].coroutine_name is not None
    assert "_worker" in created[0].coroutine_name


async def test_terminal_events_emitted_on_completion(bus_and_patcher) -> None:
    bus, patcher = bus_and_patcher
    received: list[RuntimeEvent] = []
    bus.subscribe(
        received.append,
        event_types={
            "asyncio.task.created",
            "asyncio.task.completed",
            "asyncio.task.cancelled",
            "asyncio.task.failed",
        },
    )
    patcher.patch()

    async def ok() -> int:
        return 7

    async def bad() -> None:
        raise RuntimeError("nope")

    async def slow() -> None:
        await asyncio.sleep(60)

    t_ok = asyncio.create_task(ok())
    t_bad = asyncio.create_task(bad())
    t_cancel = asyncio.create_task(slow())
    t_cancel.cancel()

    await asyncio.gather(t_ok, t_bad, t_cancel, return_exceptions=True)
    await bus.join()

    completed = [e for e in received if isinstance(e, TaskCompletedEvent)]
    failed = [e for e in received if isinstance(e, TaskFailedEvent)]
    cancelled = [e for e in received if isinstance(e, TaskCancelledEvent)]
    assert len(completed) == 1
    assert len(failed) == 1
    assert failed[0].exception_type == "RuntimeError"
    assert failed[0].exception_message == "nope"
    assert len(cancelled) == 1


async def test_parent_task_id_is_linked(bus_and_patcher) -> None:
    bus, patcher = bus_and_patcher
    received: list[TaskCreatedEvent] = []
    bus.subscribe(received.append, event_types={"asyncio.task.created"})
    patcher.patch()

    async def child() -> None:
        return None

    async def parent() -> None:
        # ``child`` is created from within the parent's coroutine. asyncio's
        # current_task() resolves to the parent task, so the wrapper should
        # link the two.
        child_task = asyncio.create_task(child(), name="child-task")
        await child_task

    parent_task = asyncio.create_task(parent(), name="parent-task")
    await parent_task
    await bus.join()

    by_name = {ev.task_name: ev for ev in received}
    assert "parent-task" in by_name and "child-task" in by_name
    assert by_name["parent-task"].parent_task_id is None
    assert by_name["child-task"].parent_task_id == by_name["parent-task"].task_id


# ── safety isolation ───────────────────────────────────────────────────────


async def test_instrumentation_failure_does_not_break_task(bus_and_patcher) -> None:
    bus, patcher = bus_and_patcher
    patcher.patch()

    # A subscriber that explodes — fanout failures must never reach the
    # patched create_task wrapper.
    def angry(_event: RuntimeEvent) -> None:
        raise RuntimeError("subscriber failure")

    bus.subscribe(angry, event_types={"asyncio.task.created"})
    task = asyncio.create_task(_worker(), name="resilient")
    assert await task == 42


async def test_after_unpatch_no_events_emitted(bus_and_patcher) -> None:
    bus, patcher = bus_and_patcher
    received: list[RuntimeEvent] = []
    bus.subscribe(received.append, event_types={"asyncio.task.created"})

    patcher.patch()
    task = asyncio.create_task(_worker())
    await task
    await bus.join()
    assert len(received) == 1

    patcher.unpatch()
    task2 = asyncio.create_task(_worker())
    await task2
    await bus.join()
    assert len(received) == 1  # no new emission after unpatch


# ── concurrent task creation ────────────────────────────────────────────────


async def test_concurrent_create_task(bus_and_patcher) -> None:
    bus, patcher = bus_and_patcher
    received: list[TaskCreatedEvent] = []
    bus.subscribe(received.append, event_types={"asyncio.task.created"})
    patcher.patch()

    async def burst() -> list[asyncio.Task[int]]:
        return [asyncio.create_task(_worker()) for _ in range(50)]

    tasks_a, tasks_b = await asyncio.gather(burst(), burst())
    await asyncio.gather(*tasks_a, *tasks_b)
    await bus.join()

    assert len(received) == 100
    ids = {ev.task_id for ev in received}
    assert len(ids) == 100  # all unique
