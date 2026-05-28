from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.asyncio import AsyncioPatcher
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskFailedEvent,
    from_dict,
    to_dict,
)
from asyncviz.runtime.events.models.enums import EventType, TaskState
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


# ── model shape ────────────────────────────────────────────────────────────


def test_cancellation_event_has_cancellation_origin_field() -> None:
    event = TaskCancelledEvent(task_id="t1")
    assert event.cancellation_origin is None  # default

    explicit = TaskCancelledEvent(task_id="t1", cancellation_origin="explicit")
    assert explicit.cancellation_origin == "explicit"


def test_cancellation_event_roundtrips_with_origin() -> None:
    original = TaskCancelledEvent(
        task_id="t1",
        cancellation_origin="timeout",
        created_at=100.0,
        completed_at=100.5,
        duration_seconds=0.5,
    )
    rebuilt = from_dict(to_dict(original))
    assert isinstance(rebuilt, TaskCancelledEvent)
    assert rebuilt.cancellation_origin == "timeout"
    assert rebuilt.duration_seconds == 0.5


# ── asyncio semantics ──────────────────────────────────────────────────────


async def test_explicit_cancel_emits_cancelled_not_failed(wired) -> None:
    bus, _patcher, _registry = wired
    received: list = []
    bus.subscribe(
        received.append,
        event_types={"asyncio.task.cancelled", "asyncio.task.failed", "asyncio.task.completed"},
    )

    async def hang() -> None:
        await asyncio.sleep(60)

    task = asyncio.create_task(hang(), name="hung")
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    await bus.join()

    types = [e.event_type for e in received]
    assert types == ["asyncio.task.cancelled"]
    assert isinstance(received[0], TaskCancelledEvent)
    assert received[0].task_name == "hung"


async def test_wait_for_timeout_emits_cancelled(wired) -> None:
    bus, _patcher, _registry = wired
    received: list = []
    bus.subscribe(
        received.append,
        event_types={"asyncio.task.cancelled", "asyncio.task.failed", "asyncio.task.completed"},
    )

    async def slow() -> None:
        await asyncio.sleep(60)

    # Wrap in an explicit Task (Python 3.11+ wait_for doesn't always create
    # one itself) — we want our instrumentation to observe the task that
    # gets cancelled when the timeout fires.
    task = asyncio.create_task(slow(), name="slow-task")
    with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=0.01)
    await bus.join()

    cancelled = [e for e in received if isinstance(e, TaskCancelledEvent)]
    assert len(cancelled) == 1
    assert cancelled[0].task_name == "slow-task"


async def test_catch_cancelled_and_raise_other_emits_failed_not_cancelled(wired) -> None:
    """A task that suppresses CancelledError and raises something else should
    report as FAILED — not CANCELLED. This is the canonical asyncio
    semantic: ``task.cancelled()`` is only True if the cancellation
    actually propagated to completion."""
    bus, _patcher, _registry = wired
    received: list = []
    bus.subscribe(
        received.append,
        event_types={"asyncio.task.cancelled", "asyncio.task.failed", "asyncio.task.completed"},
    )

    async def rebel() -> None:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise ValueError("I refuse to cancel")  # noqa: B904

    task = asyncio.create_task(rebel(), name="rebel")
    # Let the coroutine reach its ``await asyncio.sleep`` before cancelling —
    # otherwise Python's strict cancel-before-start semantics produce a
    # CancelledError that bypasses the inner try/except.
    await asyncio.sleep(0)
    task.cancel()
    with contextlib.suppress(ValueError):
        await task
    await bus.join()

    types = [e.event_type for e in received]
    assert types == ["asyncio.task.failed"]
    assert isinstance(received[0], TaskFailedEvent)
    assert received[0].exception_type == "ValueError"


async def test_catch_cancelled_and_return_emits_completed(wired) -> None:
    """A task that fully swallows CancelledError completes normally — and
    our instrumentation must follow asyncio's lead: COMPLETED, not CANCELLED."""
    bus, _patcher, _registry = wired
    received: list = []
    bus.subscribe(
        received.append,
        event_types={"asyncio.task.cancelled", "asyncio.task.failed", "asyncio.task.completed"},
    )

    async def survivor() -> str:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            return "survived"
        return "no cancel"

    task = asyncio.create_task(survivor(), name="survivor")
    # See ``test_catch_cancelled_and_raise_other_emits_failed_not_cancelled``
    # for the rationale on the yield.
    await asyncio.sleep(0)
    task.cancel()
    result = await task
    await bus.join()

    assert result == "survived"
    types = [e.event_type for e in received]
    assert types == ["asyncio.task.completed"]
    assert isinstance(received[0], TaskCompletedEvent)


# ── nested / propagated cancellation ───────────────────────────────────────


async def test_parent_cancellation_cancels_awaited_children(wired) -> None:
    bus, _patcher, registry = wired
    received: list = []
    bus.subscribe(received.append, event_types={"asyncio.task.cancelled"})

    async def child() -> None:
        await asyncio.sleep(60)

    async def parent() -> None:
        child_task = asyncio.create_task(child(), name="child")
        try:
            await child_task
        except asyncio.CancelledError:
            child_task.cancel()
            raise

    parent_task = asyncio.create_task(parent(), name="parent")
    await asyncio.sleep(0.01)
    parent_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await parent_task
    await bus.join()

    cancelled_names = sorted(
        e.task_name for e in received if isinstance(e, TaskCancelledEvent) and e.task_name
    )
    assert "parent" in cancelled_names
    assert "child" in cancelled_names

    # Registry agrees with our event log.
    metrics = registry.metrics_snapshot()
    assert metrics.cancelled_tasks >= 2


# ── cancellation storm ─────────────────────────────────────────────────────


async def test_cancellation_storm_produces_unique_terminal_per_task(wired) -> None:
    bus, _patcher, registry = wired
    received: list = []
    bus.subscribe(
        received.append,
        event_types={
            "asyncio.task.cancelled",
            "asyncio.task.completed",
            "asyncio.task.failed",
        },
    )

    async def slow(i: int) -> int:
        await asyncio.sleep(60)
        return i

    tasks = [asyncio.create_task(slow(i), name=f"t{i}") for i in range(200)]
    # Storm: cancel them all at once.
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await bus.join()

    assert len(received) == 200
    # Every task has exactly one terminal event, and all of them are
    # cancellations.
    by_task = {e.task_id for e in received}
    assert len(by_task) == 200
    assert all(isinstance(e, TaskCancelledEvent) for e in received)

    metrics = registry.metrics_snapshot()
    assert metrics.cancelled_tasks == 200
    assert metrics.failed_tasks == 0
    assert metrics.completed_tasks == 0


# ── registry behavior ──────────────────────────────────────────────────────


def test_registry_per_terminal_duration_averages() -> None:
    """Completed / cancelled / failed averages should be tracked separately."""
    registry = TaskRegistry()

    for tid, dur in [("c1", 0.1), ("c2", 0.3)]:
        registry.register(tid)
        registry.handle_event(TaskCompletedEvent(task_id=tid, duration_seconds=dur))

    for tid, dur in [("x1", 1.0), ("x2", 2.0), ("x3", 3.0)]:
        registry.register(tid)
        registry.handle_event(TaskCancelledEvent(task_id=tid, duration_seconds=dur))

    registry.register("f1")
    registry.handle_event(TaskFailedEvent(task_id="f1", duration_seconds=5.0, exception_type="X"))

    metrics = registry.metrics_snapshot()
    assert metrics.completed_tasks == 2
    assert metrics.cancelled_tasks == 3
    assert metrics.failed_tasks == 1

    assert metrics.average_completed_duration_seconds is not None
    assert abs(metrics.average_completed_duration_seconds - 0.2) < 1e-9
    assert metrics.average_cancelled_duration_seconds is not None
    assert abs(metrics.average_cancelled_duration_seconds - 2.0) < 1e-9
    assert metrics.average_failed_duration_seconds == 5.0
    # Combined average should weigh all six terminations equally.
    assert metrics.average_duration_seconds is not None
    expected = (0.1 + 0.3 + 1.0 + 2.0 + 3.0 + 5.0) / 6
    assert abs(metrics.average_duration_seconds - expected) < 1e-9


def test_cancelled_state_is_immutable_in_registry() -> None:
    """Once CANCELLED, a task can't be flipped back to RUNNING / COMPLETED."""
    registry = TaskRegistry()
    registry.register("t1")
    registry.handle_event(TaskCancelledEvent(task_id="t1", duration_seconds=0.1))
    snap = registry.snapshot_task("t1")
    assert snap is not None
    assert snap.state == TaskState.CANCELLED

    # Try every kind of follow-up event — registry must absorb without
    # changing state.
    for follow_up in (
        TaskCompletedEvent(task_id="t1", duration_seconds=0.2),
        TaskFailedEvent(task_id="t1", exception_type="X"),
    ):
        registry.handle_event(follow_up)

    snap = registry.snapshot_task("t1")
    assert snap is not None
    assert snap.state == TaskState.CANCELLED
    # Duration captured by the cancellation event must persist.
    assert snap.duration_seconds == 0.1

    metrics = registry.metrics_snapshot()
    # Two invalid follow-ups rejected.
    assert metrics.rejected_transitions == 2


# ── replay ─────────────────────────────────────────────────────────────────


def test_cancellation_event_is_replay_safe() -> None:
    """from_dict(to_dict(event)) preserves every field, including origin."""
    import uuid

    rid = uuid.uuid4()
    original = TaskCancelledEvent(
        task_id="t1",
        task_name="worker",
        coroutine_name="my_coro",
        parent_task_id="p1",
        created_at=100.0,
        completed_at=100.75,
        duration_seconds=0.75,
        cancellation_origin="timeout",
        runtime_id=rid,
        source="instrumentation",
    )
    rebuilt = from_dict(to_dict(original))
    assert isinstance(rebuilt, TaskCancelledEvent)
    assert rebuilt.task_id == "t1"
    assert rebuilt.task_name == "worker"
    assert rebuilt.coroutine_name == "my_coro"
    assert rebuilt.parent_task_id == "p1"
    assert rebuilt.created_at == 100.0
    assert rebuilt.completed_at == 100.75
    assert rebuilt.duration_seconds == 0.75
    assert rebuilt.cancellation_origin == "timeout"
    assert rebuilt.runtime_id == rid


@pytest.mark.parametrize("origin", ["explicit", "timeout", "parent", "shutdown", None])
def test_cancellation_origin_accepts_protocol_values(origin: str | None) -> None:
    event = TaskCancelledEvent(task_id="t1", cancellation_origin=origin)
    assert event.cancellation_origin == origin
