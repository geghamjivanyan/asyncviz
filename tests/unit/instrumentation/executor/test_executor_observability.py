"""Metrics, tracing, configuration, diagnostics endpoint."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.instrumentation.executor import (
    DEFAULT_EXECUTOR_CONFIG,
    ExecutorInstrumentationConfig,
    ExecutorInstrumentationEngine,
    build_executor_diagnostics,
    get_executor_metrics,
    reset_executor_metrics,
    suppress_executor_instrumentation,
)
from asyncviz.instrumentation.executor.executor_tracing import (
    clear_executor_trace,
    get_executor_trace,
    set_executor_trace_enabled,
)

# ── metrics ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_count_work_lifecycle(
    engine: ExecutorInstrumentationEngine,
) -> None:
    reset_executor_metrics()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: 1)
    snap = get_executor_metrics().snapshot()
    assert snap.work_items_submitted == 1
    assert snap.work_items_started == 1
    assert snap.work_items_completed == 1


@pytest.mark.asyncio
async def test_metrics_count_suppressed_calls(
    engine: ExecutorInstrumentationEngine,
) -> None:
    reset_executor_metrics()
    loop = asyncio.get_running_loop()
    with suppress_executor_instrumentation():
        await loop.run_in_executor(None, lambda: 1)
    snap = get_executor_metrics().snapshot()
    assert snap.suppressed_calls == 1
    assert snap.work_items_submitted == 0


@pytest.mark.asyncio
async def test_metrics_track_failed(
    engine: ExecutorInstrumentationEngine,
) -> None:
    reset_executor_metrics()
    loop = asyncio.get_running_loop()

    def boom() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError):
        await loop.run_in_executor(None, boom)
    snap = get_executor_metrics().snapshot()
    assert snap.work_items_failed == 1


# ── configuration ───────────────────────────────────────────────────────


def test_default_config_emits_everything() -> None:
    cfg = DEFAULT_EXECUTOR_CONFIG
    assert cfg.emit_registered
    assert cfg.emit_submitted
    assert cfg.emit_started
    assert cfg.emit_completed
    assert cfg.emit_failed
    assert cfg.emit_cancelled


@pytest.mark.asyncio
async def test_emit_started_false_suppresses_started_events(
    bus,  # type: ignore[no-untyped-def]
) -> None:
    cfg = ExecutorInstrumentationConfig(emit_started=False)
    engine = ExecutorInstrumentationEngine(bus=bus, config=cfg)
    engine.patch()
    try:
        seen: list[str] = []
        bus.subscribe(
            lambda e: seen.append(e.event_type),
            event_types={
                "asyncio.executor.work.started",
                "asyncio.executor.work.completed",
            },
        )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: 1)
        # Yield so cross-thread publishes from the wrapper take effect
        # before we ask the bus to drain.
        for _ in range(3):
            await asyncio.sleep(0)
        await bus.join()
        assert "asyncio.executor.work.completed" in seen
        assert "asyncio.executor.work.started" not in seen
    finally:
        engine.unpatch()


# ── tracing ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tracing_disabled_by_default(
    engine: ExecutorInstrumentationEngine,
) -> None:
    clear_executor_trace()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: 1)
    assert get_executor_trace() == ()


@pytest.mark.asyncio
async def test_tracing_records_when_enabled(
    engine: ExecutorInstrumentationEngine,
) -> None:
    set_executor_trace_enabled(True)
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: 1)
        kinds = [entry.kind for entry in get_executor_trace()]
        assert "work-submitted" in kinds
        assert "work-completed" in kinds
    finally:
        set_executor_trace_enabled(False)


# ── diagnostics ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_executor_diagnostics_reports_metrics(
    engine: ExecutorInstrumentationEngine,
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: 1)
    snap = build_executor_diagnostics()
    assert snap.metrics.work_items_completed == 1
