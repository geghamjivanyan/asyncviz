from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

import pytest_asyncio

from asyncviz.instrumentation.asyncio import AsyncioPatcher
from asyncviz.instrumentation.asyncio.context import CancellationContext
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models import TaskCancelledEvent
from asyncviz.runtime.events.models.enums import EventType
from asyncviz.runtime.tasks import TaskRegistry


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


# ── CancellationContext primitives ─────────────────────────────────────────


def test_context_default_state() -> None:
    ctx = CancellationContext()
    assert ctx.shutdown_in_progress is False


def test_context_begin_end_shutdown_toggles() -> None:
    ctx = CancellationContext()
    ctx.begin_shutdown()
    assert ctx.shutdown_in_progress is True
    ctx.end_shutdown()
    assert ctx.shutdown_in_progress is False


def test_context_attribute_during_shutdown() -> None:
    ctx = CancellationContext()
    ctx.begin_shutdown()

    class FakeTask:
        def cancelling(self) -> int:
            return 1

    assert ctx.attribute(FakeTask()) == "shutdown"  # type: ignore[arg-type]


def test_context_attribute_explicit_when_cancelling_positive() -> None:
    ctx = CancellationContext()

    class FakeTask:
        def cancelling(self) -> int:
            return 2

    assert ctx.attribute(FakeTask()) == "explicit"  # type: ignore[arg-type]


def test_context_attribute_fallback_explicit_when_no_cancelling_method() -> None:
    ctx = CancellationContext()

    class FakeTask:
        pass

    assert ctx.attribute(FakeTask()) == "explicit"  # type: ignore[arg-type]


# ── explicit attribution end-to-end ────────────────────────────────────────


async def test_explicit_cancel_attributes_origin_to_explicit(wired) -> None:
    bus, _patcher, registry = wired
    received: list[TaskCancelledEvent] = []
    bus.subscribe(received.append, event_types={"asyncio.task.cancelled"})

    async def hang() -> None:
        await asyncio.sleep(60)

    task = asyncio.create_task(hang(), name="explicit-target")
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    await bus.join()

    assert len(received) == 1
    assert received[0].cancellation_origin == "explicit"

    # Registry mirrors it.
    cancelled = registry.list_cancellations_by_origin("explicit")
    assert any(t.task_name == "explicit-target" for t in cancelled)


# ── shutdown attribution end-to-end ────────────────────────────────────────


async def test_shutdown_attribution_via_context_flag(wired) -> None:
    bus, patcher, _registry = wired
    received: list[TaskCancelledEvent] = []
    bus.subscribe(received.append, event_types={"asyncio.task.cancelled"})

    async def hang() -> None:
        await asyncio.sleep(60)

    task = asyncio.create_task(hang(), name="shutdown-target")
    # Mark shutdown BEFORE cancelling so the done-callback attributes correctly.
    patcher.cancellation_context.begin_shutdown()
    try:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await bus.join()
    finally:
        patcher.cancellation_context.end_shutdown()

    assert len(received) == 1
    assert received[0].cancellation_origin == "shutdown"


async def test_mixed_storm_attributes_each_origin_correctly(wired) -> None:
    bus, patcher, registry = wired
    received: list[TaskCancelledEvent] = []
    bus.subscribe(received.append, event_types={"asyncio.task.cancelled"})

    async def hang() -> None:
        await asyncio.sleep(60)

    # Phase 1: 5 tasks cancelled explicitly (no shutdown flag).
    explicit_tasks = [asyncio.create_task(hang(), name=f"e{i}") for i in range(5)]
    for t in explicit_tasks:
        t.cancel()
    await asyncio.gather(*explicit_tasks, return_exceptions=True)

    # Phase 2: 5 more tasks cancelled during shutdown.
    shutdown_tasks = [asyncio.create_task(hang(), name=f"s{i}") for i in range(5)]
    patcher.cancellation_context.begin_shutdown()
    try:
        for t in shutdown_tasks:
            t.cancel()
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
    finally:
        patcher.cancellation_context.end_shutdown()

    await bus.join()

    explicit = [e for e in received if e.cancellation_origin == "explicit"]
    shutdown = [e for e in received if e.cancellation_origin == "shutdown"]
    assert len(explicit) == 5
    assert len(shutdown) == 5

    metrics = registry.metrics_snapshot()
    assert metrics.cancellations_by_origin.get("explicit") == 5
    assert metrics.cancellations_by_origin.get("shutdown") == 5


# ── replay serialization ───────────────────────────────────────────────────


def test_cancellation_origin_round_trip() -> None:
    from asyncviz.runtime.events.models import from_dict, to_dict

    for origin in ("explicit", "shutdown", "timeout", "parent", None):
        original = TaskCancelledEvent(task_id="t1", cancellation_origin=origin)
        rebuilt = from_dict(to_dict(original))
        assert isinstance(rebuilt, TaskCancelledEvent)
        assert rebuilt.cancellation_origin == origin


# ── registry breakdown ─────────────────────────────────────────────────────


def test_registry_cancellations_by_origin_breakdown() -> None:
    registry = TaskRegistry()
    for tid, origin in [
        ("e1", "explicit"),
        ("e2", "explicit"),
        ("e3", "explicit"),
        ("s1", "shutdown"),
        ("s2", "shutdown"),
        ("u1", None),
    ]:
        registry.register(tid)
        registry.handle_event(
            TaskCancelledEvent(task_id=tid, duration_seconds=0.1, cancellation_origin=origin)
        )

    metrics = registry.metrics_snapshot()
    assert metrics.cancellations_by_origin == {
        "explicit": 3,
        "shutdown": 2,
        "unknown": 1,
    }
    assert metrics.cancelled_tasks == 6

    explicit_tasks = registry.list_cancellations_by_origin("explicit")
    assert {t.task_id for t in explicit_tasks} == {"e1", "e2", "e3"}

    shutdown_tasks = registry.list_cancellations_by_origin("shutdown")
    assert {t.task_id for t in shutdown_tasks} == {"s1", "s2"}

    unknown_tasks = registry.list_cancellations_by_origin(None)
    assert {t.task_id for t in unknown_tasks} == {"u1"}


def test_registry_persists_cancellation_origin_in_snapshot() -> None:
    registry = TaskRegistry()
    registry.register("t1")
    registry.handle_event(
        TaskCancelledEvent(task_id="t1", duration_seconds=0.1, cancellation_origin="shutdown")
    )
    snap = registry.snapshot_task("t1")
    assert snap is not None
    assert snap.cancellation_origin == "shutdown"


def test_cancellation_origin_is_immutable_after_terminal() -> None:
    """Once a task is cancelled, follow-up events can't change the origin."""
    registry = TaskRegistry()
    registry.register("t1")
    registry.handle_event(
        TaskCancelledEvent(task_id="t1", duration_seconds=0.1, cancellation_origin="explicit")
    )
    # Try to re-cancel with a different origin — registry rejects the
    # transition, origin stays.
    registry.handle_event(
        TaskCancelledEvent(task_id="t1", duration_seconds=0.2, cancellation_origin="shutdown")
    )
    snap = registry.snapshot_task("t1")
    assert snap is not None
    assert snap.cancellation_origin == "explicit"
