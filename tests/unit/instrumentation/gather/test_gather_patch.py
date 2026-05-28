"""End-to-end behaviour tests for :class:`GatherInstrumentationEngine`."""

from __future__ import annotations

import asyncio
import gc
from collections.abc import Iterable

import pytest

from asyncviz.instrumentation.gather import (
    GatherInstrumentationEngine,
    suppress_gather_instrumentation,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.event import RuntimeEvent


async def _collect(bus: EventBus, types: Iterable[str]) -> list[RuntimeEvent]:
    collected: list[RuntimeEvent] = []

    def _on(event: RuntimeEvent) -> None:
        collected.append(event)

    bus.subscribe(_on, event_types=set(types))
    return collected


# ── patch lifecycle ──────────────────────────────────────────────────────


def test_patch_replaces_asyncio_gather(
    engine_unpatched: GatherInstrumentationEngine,
) -> None:
    original = asyncio.gather
    engine_unpatched.patch()
    assert asyncio.gather is not original
    engine_unpatched.unpatch()
    assert asyncio.gather is original


def test_patch_is_idempotent(engine_unpatched: GatherInstrumentationEngine) -> None:
    engine_unpatched.patch()
    first = asyncio.gather
    engine_unpatched.patch()
    assert asyncio.gather is first


def test_unpatch_without_patch_is_safe(
    engine_unpatched: GatherInstrumentationEngine,
) -> None:
    engine_unpatched.unpatch()
    assert not engine_unpatched.is_patched


# ── semantics preservation ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gather_preserves_result_order(
    engine: GatherInstrumentationEngine,
) -> None:
    async def slow(n: int, delay: float) -> int:
        await asyncio.sleep(delay)
        return n

    results = await asyncio.gather(slow(1, 0.01), slow(2, 0.0), slow(3, 0.005))
    assert results == [1, 2, 3]


@pytest.mark.asyncio
async def test_gather_return_exceptions_true(
    engine: GatherInstrumentationEngine,
) -> None:
    async def ok() -> int:
        return 7

    async def boom() -> int:
        raise ValueError("nope")

    results = await asyncio.gather(ok(), boom(), return_exceptions=True)
    assert results[0] == 7
    assert isinstance(results[1], ValueError)


@pytest.mark.asyncio
async def test_gather_return_exceptions_false_propagates(
    engine: GatherInstrumentationEngine,
) -> None:
    async def ok() -> int:
        return 7

    async def boom() -> int:
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        await asyncio.gather(ok(), boom())


@pytest.mark.asyncio
async def test_gather_cancellation_propagates_to_children(
    engine: GatherInstrumentationEngine,
) -> None:
    seen_cancel: list[bool] = []

    async def child() -> None:
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            seen_cancel.append(True)
            raise

    g = asyncio.gather(child(), child())
    await asyncio.sleep(0)
    g.cancel()
    with pytest.raises(asyncio.CancelledError):
        await g
    assert len(seen_cancel) == 2


@pytest.mark.asyncio
async def test_gather_empty_args_returns_completed_future(
    engine: GatherInstrumentationEngine,
) -> None:
    result = await asyncio.gather()
    assert result == []


# ── event emission ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gather_emits_created_attached_wait_completed_in_order(
    bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    events = await _collect(
        bus,
        [
            "asyncio.gather.created",
            "asyncio.gather.child.attached",
            "asyncio.gather.wait.started",
            "asyncio.gather.child.completed",
            "asyncio.gather.completed",
        ],
    )

    async def child(n: int) -> int:
        return n

    await asyncio.gather(child(1), child(2))
    await bus.join()
    kinds = [e.event_type for e in events]
    assert kinds[0] == "asyncio.gather.created"
    assert kinds.count("asyncio.gather.child.attached") == 2
    assert "asyncio.gather.wait.started" in kinds
    assert kinds.count("asyncio.gather.child.completed") == 2
    assert kinds[-1] == "asyncio.gather.completed"


@pytest.mark.asyncio
async def test_gather_completed_carries_child_count_and_duration(
    bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.gather.completed"])

    async def child(n: int) -> int:
        return n

    await asyncio.gather(child(1), child(2), child(3))
    await bus.join()
    assert len(events) == 1
    e = events[0]
    assert e.child_count == 3  # type: ignore[attr-defined]
    assert e.completed_count == 3  # type: ignore[attr-defined]
    assert e.duration_seconds is not None  # type: ignore[attr-defined]
    assert e.duration_seconds >= 0.0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_gather_cancelled_emits_cancelled_event(
    bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.gather.cancelled"])

    async def child() -> None:
        await asyncio.sleep(1)

    g = asyncio.gather(child(), child())
    await asyncio.sleep(0)
    g.cancel()
    with pytest.raises(asyncio.CancelledError):
        await g
    await bus.join()
    assert len(events) == 1


@pytest.mark.asyncio
async def test_gather_failure_emits_failed_event_with_exception_type(
    bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.gather.failed"])

    async def ok() -> int:
        return 1

    async def boom() -> int:
        raise KeyError("missing")

    with pytest.raises(KeyError):
        await asyncio.gather(ok(), boom())
    await bus.join()
    assert len(events) == 1
    assert events[0].exception_type == "KeyError"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_gather_child_completed_reports_failed_flag(
    bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.gather.child.completed"])

    async def ok() -> int:
        return 1

    async def boom() -> int:
        raise RuntimeError("nope")

    results = await asyncio.gather(ok(), boom(), return_exceptions=True)
    assert results[0] == 1
    await bus.join()
    failed = [e for e in events if e.failed]  # type: ignore[attr-defined]
    assert len(failed) == 1


# ── deterministic ids ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gather_ids_are_monotonic(
    bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.gather.created"])

    async def child() -> int:
        return 1

    await asyncio.gather(child(), child())
    await asyncio.gather(child())
    await bus.join()
    ids = [e.gather_id for e in events]  # type: ignore[attr-defined]
    assert ids == ["g-1", "g-2"]


# ── nested gather ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nested_gather_emits_independent_ids(
    bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.gather.created"])

    async def inner() -> int:
        return await asyncio.gather(asyncio.sleep(0, result=1), asyncio.sleep(0, result=2))  # type: ignore[return-value]

    await asyncio.gather(inner(), inner())
    await bus.join()
    gather_ids = {e.gather_id for e in events}  # type: ignore[attr-defined]
    # 1 outer + 2 inner = 3 distinct ids
    assert len(gather_ids) == 3


# ── internal suppression ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_suppress_gather_instrumentation_skips_events(
    bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.gather.created"])

    async def child() -> int:
        return 1

    with suppress_gather_instrumentation():
        await asyncio.gather(child(), child())
    await bus.join()
    assert events == []


# ── child task ids ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_child_attached_carries_resolved_task_ids(
    bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.gather.child.attached"])
    # The default resolver falls back to ``get_name`` — set explicit names
    # on tasks so we can assert the resolution path.
    t1 = asyncio.create_task(asyncio.sleep(0, result=1), name="alpha")
    t2 = asyncio.create_task(asyncio.sleep(0, result=2), name="beta")
    await asyncio.gather(t1, t2)
    await bus.join()
    names = sorted(e.child_task_id for e in events)  # type: ignore[attr-defined]
    assert names == ["alpha", "beta"]


@pytest.mark.asyncio
async def test_task_id_resolver_override(
    bus: EventBus,
) -> None:
    engine = GatherInstrumentationEngine(
        bus=bus,
        task_id_resolver=lambda child: f"custom-{id(child)}",
    )
    engine.patch()
    try:
        events = await _collect(bus, ["asyncio.gather.child.attached"])

        async def child(n: int) -> int:
            return n

        await asyncio.gather(child(1), child(2))
        await bus.join()
        for e in events:
            assert e.child_task_id.startswith("custom-")  # type: ignore[attr-defined]
    finally:
        engine.unpatch()


# ── high-fanout workload ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_high_fanout_workload_balances(
    bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    completed = await _collect(bus, ["asyncio.gather.completed"])
    child_completed = await _collect(bus, ["asyncio.gather.child.completed"])

    async def child(n: int) -> int:
        return n

    N = 50
    results = await asyncio.gather(*(child(i) for i in range(N)))
    await bus.join()
    assert results == list(range(N))
    assert len(completed) == 1
    assert len(child_completed) == N


# ── registry cleanup ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_registry_prunes_after_completion(
    registry, bus: EventBus, engine: GatherInstrumentationEngine,
) -> None:
    async def child() -> int:
        return 1

    await asyncio.gather(child(), child())
    await bus.join()
    # The done-callback calls ``registry.forget`` so the gather entry
    # is gone before we observe it from outside.
    gc.collect()
    assert len(registry) == 0
    assert registry.finalized_count >= 1


# ── unpatch restores behaviour ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_unpatched_gather_does_not_emit(
    bus: EventBus, engine_unpatched: GatherInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.gather.created"])

    async def child() -> int:
        return 1

    # Engine constructed but never patched — asyncio.gather is untouched.
    await asyncio.gather(child(), child())
    await bus.join()
    assert events == []
