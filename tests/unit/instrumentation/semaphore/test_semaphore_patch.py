"""End-to-end behaviour tests for :class:`SemaphoreInstrumentationEngine`."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import pytest

from asyncviz.instrumentation.semaphore import (
    PATCHED_CLASSES,
    SemaphoreInstrumentationEngine,
    mark_semaphore_internal,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.event import RuntimeEvent


async def _collect(bus: EventBus, types: Iterable[str]) -> list[RuntimeEvent]:
    """Subscribe to ``types`` and return a list updated by callback."""
    collected: list[RuntimeEvent] = []

    def _on(event: RuntimeEvent) -> None:
        collected.append(event)

    bus.subscribe(_on, event_types=set(types))
    return collected


_PATCHED_METHOD_NAMES = ("__init__", "acquire", "release")


# ── patch lifecycle ──────────────────────────────────────────────────────


def test_patch_is_idempotent(engine_unpatched: SemaphoreInstrumentationEngine) -> None:
    engine_unpatched.patch()
    first_acquire = asyncio.Semaphore.acquire
    engine_unpatched.patch()
    assert asyncio.Semaphore.acquire is first_acquire
    assert engine_unpatched.is_patched


def test_unpatch_restores_originals(
    engine_unpatched: SemaphoreInstrumentationEngine,
) -> None:
    originals = {
        cls: {name: getattr(cls, name) for name in _PATCHED_METHOD_NAMES} for cls in PATCHED_CLASSES
    }
    engine_unpatched.patch()
    assert asyncio.Semaphore.acquire is not originals[asyncio.Semaphore]["acquire"]
    engine_unpatched.unpatch()
    for cls, names in originals.items():
        for name, original in names.items():
            assert getattr(cls, name) is original, f"{cls.__name__}.{name} not restored"


def test_unpatch_without_patch_is_safe(
    engine_unpatched: SemaphoreInstrumentationEngine,
) -> None:
    engine_unpatched.unpatch()
    assert not engine_unpatched.is_patched


# ── semantics preservation ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_acquire_release_preserves_permit_count(
    engine: SemaphoreInstrumentationEngine,
) -> None:
    s = asyncio.Semaphore(2)
    assert s._value == 2
    await s.acquire()
    assert s._value == 1
    await s.acquire()
    assert s._value == 0
    s.release()
    assert s._value == 1
    s.release()
    assert s._value == 2


@pytest.mark.asyncio
async def test_bounded_semaphore_raises_on_overflow_release(
    engine: SemaphoreInstrumentationEngine,
) -> None:
    s = asyncio.BoundedSemaphore(1)
    with pytest.raises(ValueError):
        s.release()


@pytest.mark.asyncio
async def test_subclass_compatibility(
    engine: SemaphoreInstrumentationEngine,
) -> None:
    class MySemaphore(asyncio.Semaphore):
        pass

    s = MySemaphore(1)
    await s.acquire()
    s.release()


@pytest.mark.asyncio
async def test_blocked_acquire_waits_for_release(
    engine: SemaphoreInstrumentationEngine,
) -> None:
    s = asyncio.Semaphore(1)
    await s.acquire()
    order: list[str] = []

    async def waiter() -> None:
        order.append("wait")
        await s.acquire()
        order.append("acquired")

    async def releaser() -> None:
        await asyncio.sleep(0)
        order.append("release")
        s.release()

    await asyncio.gather(waiter(), releaser())
    assert order == ["wait", "release", "acquired"]


# ── event emission ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_creating_semaphore_emits_created(
    bus: EventBus,
    engine: SemaphoreInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.semaphore.created"])
    asyncio.Semaphore(3)
    await bus.join()
    assert len(events) == 1
    e = events[0]
    assert e.semaphore_kind == "Semaphore"  # type: ignore[attr-defined]
    assert e.initial_value == 3  # type: ignore[attr-defined]
    assert e.semaphore_id.startswith("s-")  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_bounded_semaphore_emits_bound_value(
    bus: EventBus,
    engine: SemaphoreInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.semaphore.created"])
    asyncio.BoundedSemaphore(5)
    await bus.join()
    assert len(events) == 1
    e = events[0]
    assert e.semaphore_kind == "BoundedSemaphore"  # type: ignore[attr-defined]
    assert e.initial_value == 5  # type: ignore[attr-defined]
    assert e.bound_value == 5  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_acquire_release_emit_paired_events(
    bus: EventBus,
    engine: SemaphoreInstrumentationEngine,
) -> None:
    events = await _collect(
        bus,
        [
            "asyncio.semaphore.acquire.started",
            "asyncio.semaphore.acquired",
            "asyncio.semaphore.released",
        ],
    )
    s = asyncio.Semaphore(1)
    await s.acquire()
    s.release()
    await bus.join()
    kinds = [e.event_type for e in events]
    assert kinds == [
        "asyncio.semaphore.acquire.started",
        "asyncio.semaphore.acquired",
        "asyncio.semaphore.released",
    ]


@pytest.mark.asyncio
async def test_blocked_acquire_emits_wait_seconds(
    bus: EventBus,
    engine: SemaphoreInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.semaphore.acquired"])
    s = asyncio.Semaphore(1)
    await s.acquire()

    async def waiter() -> None:
        await s.acquire()

    async def releaser() -> None:
        await asyncio.sleep(0)
        s.release()

    await asyncio.gather(waiter(), releaser())
    await bus.join()
    blocked_events = [e for e in events if e.blocked]  # type: ignore[attr-defined]
    assert blocked_events
    assert blocked_events[0].wait_seconds is not None  # type: ignore[attr-defined]
    assert blocked_events[0].wait_seconds >= 0.0  # type: ignore[attr-defined]


# ── contention detection ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contention_detected_fires_on_blocked_waiter(
    bus: EventBus,
    engine: SemaphoreInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.semaphore.contention.detected"])
    s = asyncio.Semaphore(1)
    await s.acquire()

    async def waiter() -> None:
        await s.acquire()

    async def releaser() -> None:
        await asyncio.sleep(0)
        s.release()

    await asyncio.gather(waiter(), releaser())
    await bus.join()
    assert len(events) == 1
    e = events[0]
    assert e.waiter_count == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_contention_does_not_re_fire_on_subsequent_waiters(
    bus: EventBus,
    engine: SemaphoreInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.semaphore.contention.detected"])
    s = asyncio.Semaphore(1)
    await s.acquire()

    async def waiter() -> None:
        await s.acquire()

    async def releaser_eventually() -> None:
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        s.release()
        s.release()
        s.release()

    await asyncio.gather(waiter(), waiter(), waiter(), releaser_eventually())
    await bus.join()
    # First blocked waiter fires, but additional waiters do NOT re-fire the
    # leading-edge event.
    assert len(events) == 1


# ── cancellation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancelled_acquire_emits_wait_cancelled(
    bus: EventBus,
    engine: SemaphoreInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.semaphore.wait.cancelled"])
    s = asyncio.Semaphore(1)
    await s.acquire()
    task = asyncio.create_task(s.acquire())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await bus.join()
    assert len(events) == 1


# ── internal opt-out ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_internal_marker_skips_instrumentation(
    bus: EventBus,
    engine: SemaphoreInstrumentationEngine,
) -> None:
    events = await _collect(
        bus,
        [
            "asyncio.semaphore.created",
            "asyncio.semaphore.acquired",
            "asyncio.semaphore.released",
        ],
    )
    s = asyncio.Semaphore(1)
    mark_semaphore_internal(s)
    await s.acquire()
    s.release()
    await bus.join()
    # __init__ ran *before* the marker was set, so one created event is
    # expected. All subsequent events must be silent.
    non_created = [e for e in events if e.event_type != "asyncio.semaphore.created"]
    assert non_created == []


# ── deterministic ids ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_semaphore_ids_are_unique_and_monotonic(
    bus: EventBus,
    engine: SemaphoreInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.semaphore.created"])
    sems = [asyncio.Semaphore(1) for _ in range(5)]
    await bus.join()
    ids = [e.semaphore_id for e in events]  # type: ignore[attr-defined]
    assert ids == [f"s-{i}" for i in range(1, 6)]
    assert len(sems) == 5


# ── high-contention workload ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_high_contention_workload_acquire_release_balance(
    bus: EventBus,
    engine: SemaphoreInstrumentationEngine,
) -> None:
    acquired = await _collect(bus, ["asyncio.semaphore.acquired"])
    released = await _collect(bus, ["asyncio.semaphore.released"])
    s = asyncio.Semaphore(3)
    N = 50

    async def worker() -> None:
        await s.acquire()
        await asyncio.sleep(0)
        s.release()

    await asyncio.gather(*(worker() for _ in range(N)))
    await bus.join()
    assert len(acquired) == N
    assert len(released) == N
    assert s._value == 3  # all permits returned
