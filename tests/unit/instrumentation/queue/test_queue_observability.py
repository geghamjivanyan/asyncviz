"""Metrics, tracing, configuration knobs, and diagnostics endpoint surface."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.instrumentation.queue import (
    DEFAULT_QUEUE_CONFIG,
    QueueInstrumentationConfig,
    QueueInstrumentationEngine,
    build_queue_diagnostics,
    get_queue_metrics,
    reset_queue_metrics,
)
from asyncviz.instrumentation.queue.queue_tracing import (
    clear_queue_trace,
    get_queue_trace,
    set_queue_trace_enabled,
)

# ── metrics ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_count_put_get_and_registrations(
    engine: QueueInstrumentationEngine,
) -> None:
    reset_queue_metrics()
    q: asyncio.Queue[int] = asyncio.Queue()
    await q.put(1)
    _ = await q.get()
    snap = get_queue_metrics().snapshot()
    assert snap.queues_registered == 1
    assert snap.put_events == 1
    assert snap.get_events == 1


@pytest.mark.asyncio
async def test_metrics_track_blocked_events(
    engine: QueueInstrumentationEngine,
) -> None:
    reset_queue_metrics()
    q: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
    q.put_nowait(1)

    async def _producer() -> None:
        await q.put(2)

    async def _consumer() -> None:
        await asyncio.sleep(0)
        await q.get()

    await asyncio.gather(_producer(), _consumer())
    snap = get_queue_metrics().snapshot()
    assert snap.blocked_puts >= 1
    assert snap.full_waits >= 1


# ── config knobs ─────────────────────────────────────────────────────────


def test_default_config_emits_everything() -> None:
    cfg = DEFAULT_QUEUE_CONFIG
    assert cfg.emit_created
    assert cfg.emit_put_get
    assert cfg.emit_wait_events
    assert cfg.emit_task_done
    assert cfg.emit_cancelled


@pytest.mark.asyncio
async def test_emit_put_get_false_suppresses_those_events(
    bus,  # type: ignore[no-untyped-def]
) -> None:
    cfg = QueueInstrumentationConfig(emit_put_get=False)
    engine = QueueInstrumentationEngine(bus=bus, config=cfg)
    engine.patch()
    try:
        seen: list[str] = []
        bus.subscribe(
            lambda e: seen.append(e.event_type),
            event_types={
                "asyncio.queue.created",
                "asyncio.queue.put",
                "asyncio.queue.get",
            },
        )
        q: asyncio.Queue[int] = asyncio.Queue()
        await q.put(1)
        _ = await q.get()
        await bus.join()
        assert "asyncio.queue.created" in seen
        assert "asyncio.queue.put" not in seen
        assert "asyncio.queue.get" not in seen
    finally:
        engine.unpatch()


@pytest.mark.asyncio
async def test_emit_created_false_suppresses_creation_event(
    bus,  # type: ignore[no-untyped-def]
) -> None:
    cfg = QueueInstrumentationConfig(emit_created=False)
    engine = QueueInstrumentationEngine(bus=bus, config=cfg)
    engine.patch()
    try:
        seen: list[str] = []
        bus.subscribe(
            lambda e: seen.append(e.event_type),
            event_types={"asyncio.queue.created"},
        )
        asyncio.Queue()
        await bus.join()
        assert seen == []
    finally:
        engine.unpatch()


# ── tracing ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tracing_disabled_by_default(engine: QueueInstrumentationEngine) -> None:
    clear_queue_trace()
    asyncio.Queue()
    assert get_queue_trace() == ()


@pytest.mark.asyncio
async def test_tracing_records_when_enabled(
    engine: QueueInstrumentationEngine,
) -> None:
    set_queue_trace_enabled(True)
    try:
        q: asyncio.Queue[int] = asyncio.Queue()
        await q.put(1)
        kinds = [entry.kind for entry in get_queue_trace()]
        assert "queue-registered" in kinds
        assert "queue-put" in kinds
    finally:
        set_queue_trace_enabled(False)


# ── diagnostics ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_queue_diagnostics_reflects_registry(
    engine: QueueInstrumentationEngine,
) -> None:
    _queues = [asyncio.Queue() for _ in range(3)]
    snap = build_queue_diagnostics()
    assert snap.registry_size == 3
    kinds = {q["queue_kind"] for q in snap.queues}
    assert kinds == {"Queue"}
