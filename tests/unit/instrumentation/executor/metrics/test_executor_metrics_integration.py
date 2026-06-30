"""End-to-end: patched run_in_executor → bus → metrics engine."""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.executor import (
    ExecutorInstrumentationEngine,
    reset_default_executor_registry,
    reset_default_work_item_registry,
    reset_executor_metrics,
)
from asyncviz.instrumentation.executor.metrics import (
    ExecutorMetricsConfig,
    ExecutorMetricsEngine,
    build_executor_metrics_diagnostics,
)
from asyncviz.runtime.events import EventBus


@pytest_asyncio.fixture
async def stack() -> AsyncIterator[
    tuple[EventBus, ExecutorInstrumentationEngine, ExecutorMetricsEngine]
]:
    reset_default_executor_registry()
    reset_default_work_item_registry()
    reset_executor_metrics()
    bus = EventBus()
    await bus.start()
    patcher = ExecutorInstrumentationEngine(bus=bus)
    engine = ExecutorMetricsEngine(
        bus=bus,
        config=ExecutorMetricsConfig(
            updated_min_interval_seconds=0.0,
            updated_min_event_delta=1,
        ),
    )
    patcher.patch()
    engine.start()
    try:
        yield bus, patcher, engine
    finally:
        engine.stop()
        patcher.unpatch()
        await bus.stop()


@pytest.mark.asyncio
async def test_engine_observes_executor_events_through_bus(
    stack: tuple[EventBus, ExecutorInstrumentationEngine, ExecutorMetricsEngine],
) -> None:
    bus, _, engine = stack
    loop = asyncio.get_running_loop()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="stack")
    try:
        await loop.run_in_executor(pool, lambda: 1)
        # Yield so the executor-thread emissions reach the bus then
        # drain the queue.
        for _ in range(3):
            await asyncio.sleep(0)
        await bus.join()
    finally:
        pool.shutdown(wait=True)
    snap = engine.snapshot()
    assert any(r.executor_id for r in snap.executors)
    record = next(r for r in snap.executors if r.executor_kind == "Thread")
    assert record.throughput.completions == 1
    assert record.utilization.peak_active_workers >= 1


@pytest.mark.asyncio
async def test_diagnostics_snapshot_includes_live_executor(
    stack: tuple[EventBus, ExecutorInstrumentationEngine, ExecutorMetricsEngine],
) -> None:
    bus, _, engine = stack
    loop = asyncio.get_running_loop()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="diag")
    try:
        await loop.run_in_executor(pool, lambda: 1)
        for _ in range(3):
            await asyncio.sleep(0)
        await bus.join()
    finally:
        pool.shutdown(wait=True)
    diagnostics = build_executor_metrics_diagnostics(engine.snapshot())
    body = diagnostics.to_dict()
    assert body["snapshot"]["executors"]
    import json

    json.dumps(body)


@pytest.mark.asyncio
async def test_aggregated_event_round_trips_through_bus(
    stack: tuple[EventBus, ExecutorInstrumentationEngine, ExecutorMetricsEngine],
) -> None:
    bus, _, _ = stack
    seen: list = []
    bus.subscribe(
        lambda e: seen.append(e),
        event_types={
            "asyncio.executor.metrics.updated",
            "asyncio.executor.saturation.changed",
            "asyncio.executor.contention.detected",
        },
    )
    loop = asyncio.get_running_loop()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="roundtrip")
    try:
        for i in range(4):
            await loop.run_in_executor(pool, lambda i=i: i)
        for _ in range(3):
            await asyncio.sleep(0)
        await bus.join()
    finally:
        pool.shutdown(wait=True)
    assert any(getattr(e, "event_type", None) == "asyncio.executor.metrics.updated" for e in seen)
