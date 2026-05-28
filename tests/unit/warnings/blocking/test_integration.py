"""Integration: emitter → bus → warning manager → app lifespan."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.runtime.clock import RuntimeClock, reset_runtime_clock
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.monitoring.blocking import BlockingSeverity
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.runtime.warnings import RuntimeWarningManager
from asyncviz.runtime.warnings.blocking import (
    BlockingWarningConfiguration,
    BlockingWarningEmitter,
)
from asyncviz.runtime.warnings.blocking.utils import (
    build_synthetic_outcome,
    build_synthetic_window,
)


@pytest.fixture(autouse=True)
def _reset_clock():
    yield
    reset_runtime_clock()


async def test_emitter_drives_warning_manager_via_bus() -> None:
    """Emitter publishes → manager subscribes → grouped warning lifecycle."""
    bus = EventBus()
    await bus.start()
    try:
        clock = RuntimeClock()
        registry = TaskRegistry()
        manager = RuntimeWarningManager(registry, clock=clock)
        bus.subscribe(manager.apply_event)

        emitter = BlockingWarningEmitter(
            runtime_clock=clock,
            configuration=BlockingWarningConfiguration(
                min_severity=BlockingSeverity.CRITICAL,
                active_cooldown_ns=0,
            ),
            event_emitter=bus.publish,
        )

        win = build_synthetic_window()
        emitter.on_detection(
            build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
        )
        await asyncio.sleep(0.05)
        warnings = manager.active_view()
        types = {w.warning_type for w in warnings}
        assert "blocking_warning_group" in types
    finally:
        await bus.stop()


async def test_window_close_updates_warning_lifecycle() -> None:
    """A recovered transition refreshes the lifecycle so dashboards see RECOVERED."""
    bus = EventBus()
    await bus.start()
    try:
        clock = RuntimeClock()
        registry = TaskRegistry()
        manager = RuntimeWarningManager(registry, clock=clock)
        bus.subscribe(manager.apply_event)

        emitter = BlockingWarningEmitter(
            runtime_clock=clock,
            configuration=BlockingWarningConfiguration(
                min_severity=BlockingSeverity.CRITICAL,
                active_cooldown_ns=0,
            ),
            event_emitter=bus.publish,
        )

        win = build_synthetic_window()
        emitter.on_detection(
            build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=win, scheduled_ns=0)
        )
        closed = build_synthetic_window()
        emitter.on_detection(
            build_synthetic_outcome(
                severity=BlockingSeverity.NONE,
                lag_ns=0,
                scheduled_ns=1_000_000_000,
                closed_window=closed,
            )
        )
        await asyncio.sleep(0.05)
        # The warning manager refreshes the same lifecycle; metadata
        # carries the recovered state.
        warnings = manager.active_view()
        matching = [w for w in warnings if w.warning_type == "blocking_warning_group"]
        assert matching, "expected at least one blocking_warning_group lifecycle"
        meta = matching[0].metadata
        # Either the last transition is recovered, or the state is.
        assert meta.get("transition") == "recovered" or meta.get("state") == "recovered"
    finally:
        await bus.stop()


def test_create_app_wires_emitter() -> None:
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
    emitter: BlockingWarningEmitter = app.state.blocking_warning_emitter
    assert emitter is not None
    assert emitter.is_running is False  # not started yet (lifespan not entered)
    # The shutdown coordinator captured the reference.
    assert app.state.shutdown_coordinator._blocking_warning_emitter is emitter


def test_emitter_endpoint_returns_snapshot() -> None:
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
        assert app.state.blocking_warning_emitter.is_running is True
        # Bindings established
        assert app.state.blocking_warning_emitter.bound_detector is app.state.blocking_detector
        assert (
            app.state.blocking_warning_emitter.bound_capture_engine
            is app.state.stack_capture_engine
        )
        r = client.get("/api/runtime/warnings/blocking")
        assert r.status_code == 200
        body = r.json()
        for key in (
            "runtime_id",
            "state",
            "statistics",
            "metrics",
            "active_groups",
            "recent_groups",
        ):
            assert key in body

        r2 = client.get("/api/runtime/warnings/blocking/diagnostics")
        assert r2.status_code == 200
        assert "backpressure" in r2.json()

        r3 = client.post("/api/runtime/warnings/blocking/sweep_expirations")
        assert r3.status_code == 200
        assert "expired" in r3.json()
    assert app.state.blocking_warning_emitter.state.value == "stopped"
