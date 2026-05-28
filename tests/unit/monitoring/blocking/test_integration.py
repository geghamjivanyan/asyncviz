"""End-to-end: detector → bus → warning manager → app lifespan."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.runtime.clock import RuntimeClock, reset_runtime_clock
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.monitoring.blocking import (
    BlockingDetectorConfiguration,
    BlockingThresholdDetector,
    BlockingThresholdPolicy,
)
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.runtime.warnings import RuntimeWarningManager

from ._helpers import measure_and_evaluate


@pytest.fixture(autouse=True)
def _reset_clock():
    yield
    reset_runtime_clock()


async def test_detector_drives_warning_manager_via_bus() -> None:
    bus = EventBus()
    await bus.start()
    try:
        clock = RuntimeClock()
        registry = TaskRegistry()
        manager = RuntimeWarningManager(registry, clock=clock)

        def on_event(event):
            manager.apply_event(event)

        bus.subscribe(on_event)

        # Tight policy to make every WARNING fire (single sample).
        detector = BlockingThresholdDetector(
            runtime_clock=clock,
            configuration=BlockingDetectorConfiguration(
                cooldown_warning_ns=0,  # disable cooldown for deterministic count
                cooldown_critical_ns=0,
                thresholds=BlockingThresholdPolicy(escalation_warning_threshold=100),
            ),
            event_emitter=bus.publish,
        )
        # Feed one WARNING.
        m, e = measure_and_evaluate(1_000_000, index=0)
        detector.process(m, e)
        await asyncio.sleep(0.05)
        warnings = manager.active_view()
        assert any(w.detector == "blocking_violation" for w in warnings)
    finally:
        await bus.stop()


async def test_window_closed_creates_summary_warning() -> None:
    bus = EventBus()
    await bus.start()
    try:
        clock = RuntimeClock()
        registry = TaskRegistry()
        manager = RuntimeWarningManager(registry, clock=clock)
        bus.subscribe(manager.apply_event)

        detector = BlockingThresholdDetector(
            runtime_clock=clock,
            configuration=BlockingDetectorConfiguration(
                cooldown_warning_ns=0,
                thresholds=BlockingThresholdPolicy(
                    escalation_warning_threshold=100,
                    window_close_consecutive_normals=2,
                ),
            ),
            event_emitter=bus.publish,
        )
        detector.process(*measure_and_evaluate(1_000_000, index=0, scheduled_ns=0))
        detector.process(*measure_and_evaluate(0, index=1, scheduled_ns=10_000))
        detector.process(*measure_and_evaluate(0, index=2, scheduled_ns=20_000))
        await asyncio.sleep(0.05)
        warnings = manager.active_view()
        types = {w.warning_type for w in warnings}
        assert "blocking_violation:window_closed" in types
    finally:
        await bus.stop()


def test_create_app_wires_blocking_detector_lifecycle() -> None:
    """Verify the app pipeline starts + stops the detector cleanly."""
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
    detector: BlockingThresholdDetector = app.state.blocking_detector
    assert detector is not None
    assert detector.is_running is False  # not started yet (lifespan not entered)
    # The shutdown coordinator captured the reference.
    assert app.state.shutdown_coordinator._blocking_detector is detector


def test_blocking_endpoint_returns_snapshot() -> None:
    from fastapi.testclient import TestClient

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
    with TestClient(app) as client:
        # Now the lifespan has started — detector is running + bound.
        assert app.state.blocking_detector.is_running is True
        assert app.state.blocking_detector.bound_monitor is app.state.lag_monitor
        r = client.get("/api/runtime/monitoring/blocking")
        assert r.status_code == 200
        body = r.json()
        assert body["state"] == "running"
        assert "statistics" in body
        assert "metrics" in body

        r2 = client.get("/api/runtime/monitoring/blocking/diagnostics")
        assert r2.status_code == 200
        assert "trace" in r2.json()
    # Lifespan exited → detector stopped.
    assert app.state.blocking_detector.state.value == "stopped"
