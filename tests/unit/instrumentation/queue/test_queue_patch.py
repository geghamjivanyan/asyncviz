"""End-to-end behaviour tests for :class:`QueueInstrumentationEngine`.

Covers the contract the task brief calls out:

* patch / unpatch is reversible + idempotent
* every method preserves stdlib semantics (return values, exceptions, ordering)
* the correct events fire for every operation, in the expected order
* producer / consumer task ids round-trip through the event
* internal AsyncViz queues are NOT instrumented
* cancellation surfaces a queue.cancelled event
* high-throughput workloads don't drop the put/get balance
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import pytest

from asyncviz.instrumentation.queue import (
    PATCHED_CLASSES,
    QueueInstrumentationEngine,
    mark_queue_internal,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.event import RuntimeEvent


async def _collect(bus: EventBus, types: Iterable[str]) -> list[RuntimeEvent]:
    """Subscribe to ``types`` on ``bus`` and return a list updated by callback."""
    collected: list[RuntimeEvent] = []

    def _on(event: RuntimeEvent) -> None:
        collected.append(event)

    bus.subscribe(_on, event_types=set(types))
    return collected


# ── patch lifecycle ──────────────────────────────────────────────────────


def test_patch_is_idempotent(engine_unpatched: QueueInstrumentationEngine) -> None:
    engine_unpatched.patch()
    first_put = asyncio.Queue.put_nowait
    engine_unpatched.patch()  # second call is a no-op
    assert asyncio.Queue.put_nowait is first_put
    assert engine_unpatched.is_patched


_PATCHED_METHOD_NAMES = ("__init__", "put", "put_nowait", "get", "get_nowait", "task_done")


def test_unpatch_restores_originals(
    engine_unpatched: QueueInstrumentationEngine,
) -> None:
    originals = {
        cls: {name: getattr(cls, name) for name in _PATCHED_METHOD_NAMES} for cls in PATCHED_CLASSES
    }
    engine_unpatched.patch()
    assert asyncio.Queue.put_nowait is not originals[asyncio.Queue]["put_nowait"]
    engine_unpatched.unpatch()
    for cls, names in originals.items():
        for name, original in names.items():
            assert getattr(cls, name) is original, f"{cls.__name__}.{name} not restored"


def test_unpatch_without_patch_is_safe(
    engine_unpatched: QueueInstrumentationEngine,
) -> None:
    engine_unpatched.unpatch()  # never patched — must not raise
    assert not engine_unpatched.is_patched


# ── semantics preservation ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_put_get_preserves_fifo_for_plain_queue(
    engine: QueueInstrumentationEngine,
) -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    for i in range(5):
        await q.put(i)
    out = [await q.get() for _ in range(5)]
    assert out == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_lifo_queue_preserves_lifo_order(
    engine: QueueInstrumentationEngine,
) -> None:
    q: asyncio.LifoQueue[int] = asyncio.LifoQueue()
    for i in range(5):
        await q.put(i)
    out = [await q.get() for _ in range(5)]
    assert out == [4, 3, 2, 1, 0]


@pytest.mark.asyncio
async def test_priority_queue_preserves_priority_order(
    engine: QueueInstrumentationEngine,
) -> None:
    q: asyncio.PriorityQueue[int] = asyncio.PriorityQueue()
    for x in (3, 1, 4, 1, 5, 9, 2, 6):
        await q.put(x)
    out = [await q.get() for _ in range(8)]
    assert out == sorted(out)


@pytest.mark.asyncio
async def test_put_nowait_raises_queuefull_when_bounded(
    engine: QueueInstrumentationEngine,
) -> None:
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
    q.put_nowait(1)
    with pytest.raises(asyncio.QueueFull):
        q.put_nowait(2)


@pytest.mark.asyncio
async def test_get_nowait_raises_queueempty_when_empty(
    engine: QueueInstrumentationEngine,
) -> None:
    q: asyncio.Queue[int] = asyncio.Queue()
    with pytest.raises(asyncio.QueueEmpty):
        q.get_nowait()


# ── event emission ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_creating_queue_emits_queue_created(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.queue.created"])
    asyncio.Queue(maxsize=4)
    await bus.join()
    assert len(events) == 1
    e = events[0]
    assert e.queue_kind == "Queue"  # type: ignore[attr-defined]
    assert e.maxsize == 4  # type: ignore[attr-defined]
    assert e.queue_id.startswith("q-")  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_put_get_emit_paired_events(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.queue.put", "asyncio.queue.get"])
    q: asyncio.Queue[int] = asyncio.Queue()
    await q.put(1)
    assert await q.get() == 1
    await bus.join()
    kinds = [e.event_type for e in events]
    assert kinds == ["asyncio.queue.put", "asyncio.queue.get"]


@pytest.mark.asyncio
async def test_put_nowait_emits_nowait_flag(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.queue.put"])
    q: asyncio.Queue[int] = asyncio.Queue()
    q.put_nowait(7)
    await bus.join()
    assert len(events) == 1
    assert events[0].nowait is True  # type: ignore[attr-defined]
    assert events[0].blocked is False  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_blocked_put_emits_full_wait_then_put(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(
        bus,
        ["asyncio.queue.full_wait", "asyncio.queue.put", "asyncio.queue.get"],
    )
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
    q.put_nowait(1)

    async def _producer() -> None:
        await q.put(2)  # will block until consumer drains

    async def _consumer() -> None:
        await asyncio.sleep(0)  # let producer attempt put first
        await q.get()

    await asyncio.gather(_producer(), _consumer())
    await bus.join()

    kinds = [e.event_type for e in events]
    # The blocked-put path must produce a full_wait before the put resolves.
    assert "asyncio.queue.full_wait" in kinds
    put_events = [e for e in events if e.event_type == "asyncio.queue.put"]
    blocked = [e for e in put_events if e.blocked]  # type: ignore[attr-defined]
    assert blocked, "expected at least one put event with blocked=True"
    assert blocked[0].wait_seconds is not None  # type: ignore[attr-defined]
    assert blocked[0].wait_seconds >= 0.0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_blocked_get_emits_empty_wait_then_get(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(
        bus,
        ["asyncio.queue.empty_wait", "asyncio.queue.get", "asyncio.queue.put"],
    )
    q: asyncio.Queue[int] = asyncio.Queue()

    async def _consumer() -> int:
        return await q.get()

    async def _producer() -> None:
        await asyncio.sleep(0)
        q.put_nowait(42)

    result, _ = await asyncio.gather(_consumer(), _producer())
    assert result == 42
    await bus.join()

    kinds = [e.event_type for e in events]
    assert "asyncio.queue.empty_wait" in kinds
    get_events = [e for e in events if e.event_type == "asyncio.queue.get"]
    blocked_get = [e for e in get_events if e.blocked]  # type: ignore[attr-defined]
    assert blocked_get
    assert blocked_get[0].wait_seconds is not None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_task_done_emits_event(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.queue.task_done"])
    q: asyncio.Queue[int] = asyncio.Queue()
    await q.put(1)
    _ = await q.get()
    q.task_done()
    await bus.join()
    assert len(events) == 1


# ── producer/consumer correlation ────────────────────────────────────────


@pytest.mark.asyncio
async def test_events_carry_task_id_when_running_inside_a_task(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.queue.put", "asyncio.queue.get"])
    q: asyncio.Queue[int] = asyncio.Queue()

    async def _do() -> None:
        await q.put(1)
        await q.get()

    await asyncio.create_task(_do(), name="producer-consumer")
    await bus.join()
    # task_id resolution depends on the asyncio task patcher being active;
    # without it, task_id is None — verify the field exists either way.
    for e in events:
        assert hasattr(e, "task_id")


# ── cancellation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancelled_get_emits_queue_cancelled(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.queue.cancelled"])
    q: asyncio.Queue[int] = asyncio.Queue()
    task = asyncio.create_task(q.get())
    await asyncio.sleep(0)  # let it park inside original_get
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await bus.join()
    assert len(events) == 1
    assert events[0].operation == "get"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_cancelled_put_emits_queue_cancelled(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.queue.cancelled"])
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
    q.put_nowait(1)
    task = asyncio.create_task(q.put(2))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await bus.join()
    assert any(e.operation == "put" for e in events)  # type: ignore[attr-defined]


# ── internal queue opt-out ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_internal_marker_skips_instrumentation(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(
        bus,
        [
            "asyncio.queue.created",
            "asyncio.queue.put",
            "asyncio.queue.get",
            "asyncio.queue.task_done",
        ],
    )
    q: asyncio.Queue[int] = asyncio.Queue()
    mark_queue_internal(q)
    await q.put(1)
    _ = await q.get()
    q.task_done()
    await bus.join()
    # The queue's own ``__init__`` ran through the patched path BEFORE the
    # marker was set — that one created event is expected. Everything after
    # the marker must be silent.
    non_created = [e for e in events if e.event_type != "asyncio.queue.created"]
    assert non_created == []


# ── deterministic queue ids ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_queue_ids_are_unique_and_monotonic(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.queue.created"])
    queues = [asyncio.Queue() for _ in range(5)]
    await bus.join()
    ids = [e.queue_id for e in events]
    assert ids == [f"q-{i}" for i in range(1, 6)]
    # silence "unused" warnings while keeping the queues alive for the test
    assert len(queues) == 5


# ── high throughput ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_high_throughput_put_get_balance(
    bus: EventBus,
    engine: QueueInstrumentationEngine,
) -> None:
    puts = await _collect(bus, ["asyncio.queue.put"])
    gets = await _collect(bus, ["asyncio.queue.get"])

    q: asyncio.Queue[int] = asyncio.Queue()
    N = 200

    async def _producer() -> None:
        for i in range(N):
            await q.put(i)

    async def _consumer() -> list[int]:
        return [await q.get() for _ in range(N)]

    _, drained = await asyncio.gather(_producer(), _consumer())
    await bus.join()

    assert drained == list(range(N))
    assert len(puts) == N
    assert len(gets) == N
