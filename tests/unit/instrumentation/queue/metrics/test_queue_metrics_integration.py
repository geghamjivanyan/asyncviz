"""End-to-end test: patched asyncio.Queue → bus → metrics engine.

These tests exercise the full chain — they don't replace the unit
tests above but prove that the engine actually receives the events the
patched queues emit, and that the diagnostics endpoint surface reflects
the live aggregate state.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.queue import (
    QueueInstrumentationEngine,
    reset_default_queue_registry,
)
from asyncviz.instrumentation.queue.metrics import (
    QueueMetricsConfig,
    QueueMetricsEngine,
    build_queue_metrics_diagnostics,
)
from asyncviz.runtime.events import EventBus


@pytest_asyncio.fixture
async def stack() -> AsyncIterator[tuple[EventBus, QueueInstrumentationEngine, QueueMetricsEngine]]:
    """Wire the bus + queue patcher + metrics engine, then tear down cleanly."""
    reset_default_queue_registry()
    bus = EventBus()
    await bus.start()
    patcher = QueueInstrumentationEngine(bus=bus)
    engine = QueueMetricsEngine(
        bus=bus,
        config=QueueMetricsConfig(
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
        reset_default_queue_registry()


@pytest.mark.asyncio
async def test_engine_observes_queue_events_through_bus(
    stack: tuple[EventBus, QueueInstrumentationEngine, QueueMetricsEngine],
) -> None:
    bus, _, engine = stack
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=4)
    for i in range(3):
        await q.put(i)
    for _ in range(2):
        _ = await q.get()
    await bus.join()
    snap = engine.snapshot()
    assert len(snap.queues) == 1
    record = snap.queues[0]
    assert record.queue_kind == "Queue"
    assert record.throughput.put_count == 3
    assert record.throughput.get_count == 2
    assert record.occupancy.peak_size == 3


@pytest.mark.asyncio
async def test_diagnostics_snapshot_includes_live_queue(
    stack: tuple[EventBus, QueueInstrumentationEngine, QueueMetricsEngine],
) -> None:
    bus, _, engine = stack
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=2)
    q.put_nowait(1)
    await bus.join()
    diagnostics = build_queue_metrics_diagnostics(engine.snapshot())
    body = diagnostics.to_dict()
    assert body["snapshot"]["queues"]
    assert body["snapshot"]["self_metrics"]["events_observed"] >= 1
    # The body is a plain JSON-safe dict — verify by round-tripping.
    import json

    json.dumps(body)
    # ensure queue reference doesn't survive for finalizer test
    del q


@pytest.mark.asyncio
async def test_aggregated_event_round_trips_through_bus(
    stack: tuple[EventBus, QueueInstrumentationEngine, QueueMetricsEngine],
) -> None:
    bus, _, _ = stack
    seen: list = []
    bus.subscribe(
        lambda e: seen.append(e),
        event_types={
            "asyncio.queue.metrics.updated",
            "asyncio.queue.pressure.changed",
        },
    )
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=4)
    for i in range(4):
        await q.put(i)
    await bus.join()
    assert any(getattr(e, "event_type", None) == "asyncio.queue.metrics.updated" for e in seen)
