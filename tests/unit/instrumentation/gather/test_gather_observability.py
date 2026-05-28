"""Metrics, tracing, configuration knobs, diagnostics endpoint."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.instrumentation.gather import (
    DEFAULT_GATHER_CONFIG,
    GatherInstrumentationConfig,
    GatherInstrumentationEngine,
    build_gather_diagnostics,
    get_gather_metrics,
    reset_gather_metrics,
    suppress_gather_instrumentation,
)
from asyncviz.instrumentation.gather.gather_tracing import (
    clear_gather_trace,
    get_gather_trace,
    set_gather_trace_enabled,
)

# ── metrics ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_count_instrumented_gathers(
    engine: GatherInstrumentationEngine,
) -> None:
    reset_gather_metrics()

    async def child() -> int:
        return 1

    await asyncio.gather(child(), child())
    snap = get_gather_metrics().snapshot()
    assert snap.gathers_instrumented == 1
    assert snap.gathers_completed == 1
    assert snap.child_completed_events == 2


@pytest.mark.asyncio
async def test_metrics_track_suppressed_calls(
    engine: GatherInstrumentationEngine,
) -> None:
    reset_gather_metrics()

    async def child() -> int:
        return 1

    with suppress_gather_instrumentation():
        await asyncio.gather(child(), child())
    snap = get_gather_metrics().snapshot()
    assert snap.suppressed_calls == 1
    # Suppressed call should NOT be recorded as instrumented.
    assert snap.gathers_instrumented == 0


@pytest.mark.asyncio
async def test_metrics_track_cancelled_and_failed(
    engine: GatherInstrumentationEngine,
) -> None:
    reset_gather_metrics()

    async def slow() -> None:
        await asyncio.sleep(1)

    g = asyncio.gather(slow(), slow())
    await asyncio.sleep(0)
    g.cancel()
    with pytest.raises(asyncio.CancelledError):
        await g

    async def boom() -> int:
        raise ValueError("nope")

    async def ok() -> int:
        return 1

    with pytest.raises(ValueError):
        await asyncio.gather(ok(), boom())

    snap = get_gather_metrics().snapshot()
    assert snap.gathers_cancelled >= 1
    assert snap.gathers_failed >= 1


# ── configuration ───────────────────────────────────────────────────────


def test_default_config_emits_everything() -> None:
    cfg = DEFAULT_GATHER_CONFIG
    assert cfg.emit_created
    assert cfg.emit_child_attached
    assert cfg.emit_wait_started
    assert cfg.emit_child_completed
    assert cfg.emit_completed
    assert cfg.emit_cancelled
    assert cfg.emit_failed


@pytest.mark.asyncio
async def test_emit_child_completed_false_suppresses_per_child_events(
    bus,  # type: ignore[no-untyped-def]
) -> None:
    cfg = GatherInstrumentationConfig(emit_child_completed=False)
    engine = GatherInstrumentationEngine(bus=bus, config=cfg)
    engine.patch()
    try:
        seen: list[str] = []
        bus.subscribe(
            lambda e: seen.append(e.event_type),
            event_types={
                "asyncio.gather.child.completed",
                "asyncio.gather.completed",
            },
        )

        async def child() -> int:
            return 1

        await asyncio.gather(child(), child())
        await bus.join()
        assert "asyncio.gather.completed" in seen
        assert "asyncio.gather.child.completed" not in seen
    finally:
        engine.unpatch()


@pytest.mark.asyncio
async def test_emit_created_false_suppresses_creation_event(
    bus,  # type: ignore[no-untyped-def]
) -> None:
    cfg = GatherInstrumentationConfig(emit_created=False)
    engine = GatherInstrumentationEngine(bus=bus, config=cfg)
    engine.patch()
    try:
        seen: list[str] = []
        bus.subscribe(
            lambda e: seen.append(e.event_type),
            event_types={"asyncio.gather.created"},
        )

        async def child() -> int:
            return 1

        await asyncio.gather(child(), child())
        await bus.join()
        assert seen == []
    finally:
        engine.unpatch()


# ── tracing ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tracing_disabled_by_default(
    engine: GatherInstrumentationEngine,
) -> None:
    clear_gather_trace()

    async def child() -> int:
        return 1

    await asyncio.gather(child(), child())
    assert get_gather_trace() == ()


@pytest.mark.asyncio
async def test_tracing_records_when_enabled(
    engine: GatherInstrumentationEngine,
) -> None:
    set_gather_trace_enabled(True)
    try:

        async def child() -> int:
            return 1

        await asyncio.gather(child(), child())
        kinds = [entry.kind for entry in get_gather_trace()]
        assert "gather-registered" in kinds
        assert "gather-completed" in kinds
    finally:
        set_gather_trace_enabled(False)


# ── diagnostics ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_gather_diagnostics_reports_metrics(
    engine: GatherInstrumentationEngine,
) -> None:
    async def child() -> int:
        return 1

    await asyncio.gather(child(), child())
    snap = build_gather_diagnostics()
    assert snap.metrics.gathers_instrumented == 1
    assert snap.metrics.gathers_completed == 1
