"""End-to-end behaviour tests for :class:`ExecutorInstrumentationEngine`."""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Iterable

import pytest

from asyncviz.instrumentation.executor import (
    ExecutorInstrumentationEngine,
    suppress_executor_instrumentation,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.event import RuntimeEvent


async def _collect(bus: EventBus, types: Iterable[str]) -> list[RuntimeEvent]:
    collected: list[RuntimeEvent] = []

    def _on(event: RuntimeEvent) -> None:
        collected.append(event)

    bus.subscribe(_on, event_types=set(types))
    return collected


async def _drain(bus: EventBus) -> None:
    """Yield the loop a couple of times so cross-thread ``call_soon_threadsafe``
    publishes (fired from inside the executor wrapper) get scheduled onto
    the bus's queue, *then* join until everything dispatches. Tests that
    use ``run_in_executor`` need this because the wrapper runs in a worker
    thread and publishes via ``call_soon_threadsafe`` — the publish enqueues
    on the next loop tick, not synchronously."""
    for _ in range(3):
        await asyncio.sleep(0)
    await bus.join()


# ── patch lifecycle ──────────────────────────────────────────────────────


def test_patch_replaces_base_event_loop_method(
    engine_unpatched: ExecutorInstrumentationEngine,
) -> None:
    original = asyncio.base_events.BaseEventLoop.run_in_executor
    engine_unpatched.patch()
    assert asyncio.base_events.BaseEventLoop.run_in_executor is not original
    engine_unpatched.unpatch()
    assert asyncio.base_events.BaseEventLoop.run_in_executor is original


def test_patch_is_idempotent(
    engine_unpatched: ExecutorInstrumentationEngine,
) -> None:
    engine_unpatched.patch()
    first = asyncio.base_events.BaseEventLoop.run_in_executor
    engine_unpatched.patch()
    assert asyncio.base_events.BaseEventLoop.run_in_executor is first


def test_unpatch_without_patch_is_safe(
    engine_unpatched: ExecutorInstrumentationEngine,
) -> None:
    engine_unpatched.unpatch()
    assert not engine_unpatched.is_patched


# ── semantics preservation ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_in_executor_returns_function_result(
    engine: ExecutorInstrumentationEngine,
) -> None:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: 42)
    assert result == 42


@pytest.mark.asyncio
async def test_run_in_executor_passes_args(
    engine: ExecutorInstrumentationEngine,
) -> None:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, pow, 2, 8)
    assert result == 256


@pytest.mark.asyncio
async def test_run_in_executor_propagates_exception(
    engine: ExecutorInstrumentationEngine,
) -> None:
    loop = asyncio.get_running_loop()

    def boom() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError):
        await loop.run_in_executor(None, boom)


@pytest.mark.asyncio
async def test_explicit_thread_pool_executor_is_supported(
    engine: ExecutorInstrumentationEngine,
) -> None:
    loop = asyncio.get_running_loop()
    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=2, thread_name_prefix="asyncviz-test",
    )
    try:
        result = await loop.run_in_executor(pool, lambda: "ok")
        assert result == "ok"
    finally:
        pool.shutdown(wait=True)


# ── event emission ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_in_executor_emits_submitted_started_completed(
    bus: EventBus, engine: ExecutorInstrumentationEngine,
) -> None:
    events = await _collect(
        bus,
        [
            "asyncio.executor.work.submitted",
            "asyncio.executor.work.started",
            "asyncio.executor.work.completed",
        ],
    )
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: 1)
    await _drain(bus)
    kinds = [e.event_type for e in events]
    assert kinds == [
        "asyncio.executor.work.submitted",
        "asyncio.executor.work.started",
        "asyncio.executor.work.completed",
    ]


@pytest.mark.asyncio
async def test_failing_work_emits_failed_event_with_exception_type(
    bus: EventBus, engine: ExecutorInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.executor.work.failed"])
    loop = asyncio.get_running_loop()

    def boom() -> None:
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        await loop.run_in_executor(None, boom)
    await _drain(bus)
    assert len(events) == 1
    assert events[0].exception_type == "RuntimeError"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_completed_event_carries_thread_name_and_duration(
    bus: EventBus, engine: ExecutorInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.executor.work.completed"])
    loop = asyncio.get_running_loop()
    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="executor-test",
    )
    try:
        await loop.run_in_executor(pool, lambda: 7)
        await _drain(bus)
        assert len(events) == 1
        e = events[0]
        assert e.duration_seconds is not None  # type: ignore[attr-defined]
        assert e.duration_seconds >= 0.0  # type: ignore[attr-defined]
        assert (e.worker_thread_name or "").startswith("executor-test")  # type: ignore[attr-defined]
    finally:
        pool.shutdown(wait=True)


@pytest.mark.asyncio
async def test_registered_event_fires_once_per_executor(
    bus: EventBus, engine: ExecutorInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.executor.registered"])
    loop = asyncio.get_running_loop()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        await loop.run_in_executor(pool, lambda: 1)
        await loop.run_in_executor(pool, lambda: 2)
        await _drain(bus)
        assert len(events) == 1
    finally:
        pool.shutdown(wait=True)


# ── cancellation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancelled_work_emits_cancelled_event(
    bus: EventBus, engine: ExecutorInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.executor.work.cancelled"])
    loop = asyncio.get_running_loop()

    def slow() -> int:
        # Use a real sleep so we can race a cancel before completion.
        import time

        time.sleep(0.5)
        return 1

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        # Submit a blocker so the second submission stays queued.
        first = loop.run_in_executor(pool, slow)
        second = loop.run_in_executor(pool, lambda: 2)
        await asyncio.sleep(0)
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second
        # let the blocker finish
        await first
        await _drain(bus)
        assert len(events) == 1
    finally:
        pool.shutdown(wait=True)


# ── internal suppression ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_suppress_executor_instrumentation_skips_events(
    bus: EventBus, engine: ExecutorInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.executor.work.submitted"])
    loop = asyncio.get_running_loop()
    with suppress_executor_instrumentation():
        await loop.run_in_executor(None, lambda: 1)
    await _drain(bus)
    assert events == []


# ── deterministic ids ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_work_item_ids_are_monotonic(
    bus: EventBus, engine: ExecutorInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.executor.work.submitted"])
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: 1)
    await loop.run_in_executor(None, lambda: 2)
    await _drain(bus)
    ids = [e.work_item_id for e in events]  # type: ignore[attr-defined]
    assert ids == ["w-1", "w-2"]


# ── high-throughput workload ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_high_throughput_workload_balances(
    bus: EventBus, engine: ExecutorInstrumentationEngine,
) -> None:
    completed = await _collect(bus, ["asyncio.executor.work.completed"])
    loop = asyncio.get_running_loop()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    try:
        N = 25
        results = await asyncio.gather(
            *(loop.run_in_executor(pool, lambda i=i: i * 2) for i in range(N)),
        )
        await _drain(bus)
        assert results == [i * 2 for i in range(N)]
        assert len(completed) == N
    finally:
        pool.shutdown(wait=True)


# ── unpatch restores behaviour ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_unpatched_run_in_executor_does_not_emit(
    bus: EventBus, engine_unpatched: ExecutorInstrumentationEngine,
) -> None:
    events = await _collect(bus, ["asyncio.executor.work.submitted"])
    loop = asyncio.get_running_loop()
    # Engine never patched — original method still in place.
    await loop.run_in_executor(None, lambda: 1)
    await _drain(bus)
    assert events == []
