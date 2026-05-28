"""Metrics, tracing, configuration knobs, and diagnostics endpoint."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.instrumentation.semaphore import (
    DEFAULT_SEMAPHORE_CONFIG,
    SemaphoreInstrumentationConfig,
    SemaphoreInstrumentationEngine,
    build_semaphore_diagnostics,
    get_semaphore_metrics,
    reset_semaphore_metrics,
)
from asyncviz.instrumentation.semaphore.semaphore_tracing import (
    clear_semaphore_trace,
    get_semaphore_trace,
    set_semaphore_trace_enabled,
)

# ── metrics ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_count_acquire_and_release(
    engine: SemaphoreInstrumentationEngine,
) -> None:
    reset_semaphore_metrics()
    s = asyncio.Semaphore(1)
    await s.acquire()
    s.release()
    snap = get_semaphore_metrics().snapshot()
    assert snap.semaphores_registered == 1
    assert snap.acquire_events == 1
    assert snap.release_events == 1


@pytest.mark.asyncio
async def test_metrics_track_blocked_acquires(
    engine: SemaphoreInstrumentationEngine,
) -> None:
    reset_semaphore_metrics()
    s = asyncio.Semaphore(1)
    await s.acquire()

    async def waiter() -> None:
        await s.acquire()

    async def releaser() -> None:
        await asyncio.sleep(0)
        s.release()

    await asyncio.gather(waiter(), releaser())
    snap = get_semaphore_metrics().snapshot()
    assert snap.blocked_acquires >= 1
    assert snap.contention_detections >= 1


# ── configuration knobs ─────────────────────────────────────────────────


def test_default_config_emits_everything() -> None:
    cfg = DEFAULT_SEMAPHORE_CONFIG
    assert cfg.emit_created
    assert cfg.emit_acquire
    assert cfg.emit_release
    assert cfg.emit_cancelled
    assert cfg.emit_contention


@pytest.mark.asyncio
async def test_emit_acquire_false_suppresses_acquire_events(
    bus,  # type: ignore[no-untyped-def]
) -> None:
    cfg = SemaphoreInstrumentationConfig(emit_acquire=False)
    engine = SemaphoreInstrumentationEngine(bus=bus, config=cfg)
    engine.patch()
    try:
        seen: list[str] = []
        bus.subscribe(
            lambda e: seen.append(e.event_type),
            event_types={
                "asyncio.semaphore.acquire.started",
                "asyncio.semaphore.acquired",
                "asyncio.semaphore.released",
            },
        )
        s = asyncio.Semaphore(1)
        await s.acquire()
        s.release()
        await bus.join()
        assert "asyncio.semaphore.acquire.started" not in seen
        assert "asyncio.semaphore.acquired" not in seen
        assert "asyncio.semaphore.released" in seen
    finally:
        engine.unpatch()


@pytest.mark.asyncio
async def test_emit_created_false_suppresses_creation_event(
    bus,  # type: ignore[no-untyped-def]
) -> None:
    cfg = SemaphoreInstrumentationConfig(emit_created=False)
    engine = SemaphoreInstrumentationEngine(bus=bus, config=cfg)
    engine.patch()
    try:
        seen: list[str] = []
        bus.subscribe(
            lambda e: seen.append(e.event_type),
            event_types={"asyncio.semaphore.created"},
        )
        asyncio.Semaphore(1)
        await bus.join()
        assert seen == []
    finally:
        engine.unpatch()


# ── tracing ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tracing_disabled_by_default(
    engine: SemaphoreInstrumentationEngine,
) -> None:
    clear_semaphore_trace()
    asyncio.Semaphore(1)
    assert get_semaphore_trace() == ()


@pytest.mark.asyncio
async def test_tracing_records_when_enabled(
    engine: SemaphoreInstrumentationEngine,
) -> None:
    set_semaphore_trace_enabled(True)
    try:
        s = asyncio.Semaphore(1)
        await s.acquire()
        kinds = [entry.kind for entry in get_semaphore_trace()]
        assert "semaphore-registered" in kinds
        assert "semaphore-acquired" in kinds
    finally:
        set_semaphore_trace_enabled(False)


# ── diagnostics ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_semaphore_diagnostics_reflects_registry(
    engine: SemaphoreInstrumentationEngine,
) -> None:
    _sems = [asyncio.Semaphore(1) for _ in range(3)]
    snap = build_semaphore_diagnostics()
    assert snap.registry_size == 3
    kinds = {s["semaphore_kind"] for s in snap.semaphores}
    assert kinds == {"Semaphore"}
