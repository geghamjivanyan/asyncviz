"""End-to-end integration: lag monitor → event bus → warning manager."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.runtime.clock import RuntimeClock
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.monitoring import EventLoopLagMonitor, LagConfiguration
from asyncviz.runtime.monitoring.event_loop import LagThresholds
from asyncviz.runtime.monitoring.event_loop.lag_measurement import calculate_lag
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.runtime.warnings import RuntimeWarningManager


@pytest.fixture
def runtime_clock() -> RuntimeClock:
    return RuntimeClock()


@pytest.fixture
def registry() -> TaskRegistry:
    return TaskRegistry()


async def test_lag_monitor_drives_warning_manager_via_bus(
    runtime_clock: RuntimeClock,
    registry: TaskRegistry,
) -> None:
    """A loop-block measurement → bus event → warning manager activates."""
    bus = EventBus()
    await bus.start()
    try:
        manager = RuntimeWarningManager(registry, clock=runtime_clock)

        # Bus → manager. Subscribe synchronously so we see the threshold
        # event flow through.
        def on_event(event):
            manager.apply_event(event)

        bus.subscribe(on_event)

        cfg = LagConfiguration(
            thresholds=LagThresholds(
                warning_seconds=0.001, critical_seconds=0.01, freeze_seconds=0.1
            ),
        )
        monitor = EventLoopLagMonitor(
            runtime_clock=runtime_clock,
            configuration=cfg,
            event_emitter=bus.publish,
        )
        m = calculate_lag(
            scheduled_ns=0,
            actual_ns=50_000_000,
            interval_ns=10_000_000,
            sample_index=0,
            runtime_id=str(runtime_clock.runtime_id),
        )
        monitor.apply_measurement(m)
        # Give the dispatcher a tick.
        await asyncio.sleep(0.05)
        warnings = manager.active_view()
        assert any(w.detector == "event_loop_lag" for w in warnings)
    finally:
        await bus.stop()


async def test_lag_monitor_lifecycle_via_app(monkeypatch) -> None:
    """The full create_app() pipeline starts + stops the monitor."""
    from asyncviz.config import AsyncVizConfig
    from asyncviz.dashboard import create_app

    config = AsyncVizConfig(
        host="127.0.0.1",
        port=8911,
        open_browser=False,
        debug=False,
        heartbeat_interval=60.0,
        enable_instrumentation=False,
    )
    app = create_app(config)
    # The lag monitor exists on app state and starts idle.
    assert app.state.lag_monitor is not None
    assert app.state.lag_monitor.is_running is False
    # The shutdown coordinator carries a reference too.
    assert app.state.shutdown_coordinator._lag_monitor is app.state.lag_monitor
