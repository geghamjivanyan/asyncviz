"""Integration: engine → bus → app lifespan + endpoints."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from asyncviz.runtime.clock import reset_runtime_clock


@pytest.fixture(autouse=True)
def _reset_clock():
    yield
    reset_runtime_clock()


def _app():
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
    return create_app(config)


def test_engine_constructed_on_app() -> None:
    app = _app()
    assert app.state.stack_capture_engine is not None
    assert app.state.shutdown_coordinator._stack_capture_engine is app.state.stack_capture_engine


def test_lifespan_starts_and_binds_engine() -> None:
    app = _app()
    with TestClient(app):
        assert app.state.stack_capture_engine.is_running is True
        assert app.state.stack_capture_engine.bound_detector is app.state.blocking_detector
    assert app.state.stack_capture_engine.state == "stopped"


def test_snapshot_endpoint_returns_200() -> None:
    app = _app()
    with TestClient(app) as client:
        r = client.get("/api/runtime/monitoring/blocking/stack_capture")
        assert r.status_code == 200
        body = r.json()
        assert "statistics" in body
        assert "metrics" in body
        assert "recent_captures" in body


def test_diagnostics_endpoint_returns_200() -> None:
    app = _app()
    with TestClient(app) as client:
        r = client.get("/api/runtime/monitoring/blocking/stack_capture/diagnostics")
        assert r.status_code == 200
        body = r.json()
        assert "backpressure" in body
        assert "trace" in body


def test_manual_capture_endpoint_returns_payload() -> None:
    app = _app()
    with TestClient(app) as client:
        r = client.post(
            "/api/runtime/monitoring/blocking/stack_capture/manual",
            json={"trigger": "demo", "severity": "NONE"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["trigger"] == "demo"
        assert isinstance(body["frames"], list)
        assert body["frame_count"] >= 1


async def test_critical_violation_through_pipeline_produces_capture() -> None:
    """End-to-end: lag monitor → detector → capture engine → snapshot."""
    from asyncviz.runtime.monitoring.event_loop.lag_measurement import calculate_lag
    from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagThresholds

    app = _app()
    with TestClient(app):
        detector = app.state.blocking_detector
        engine = app.state.stack_capture_engine

        thresholds = LagThresholds(warning_seconds=0.001, critical_seconds=0.01, freeze_seconds=0.1)
        # Feed a CRITICAL measurement directly into the detector — the
        # engine is subscribed and will fire a capture.
        m = calculate_lag(
            scheduled_ns=0,
            actual_ns=50_000_000,
            interval_ns=1_000_000,
            sample_index=0,
            runtime_id="r",
        )
        e = thresholds.evaluate(m.lag_ns)
        detector.process(m, e)
        await asyncio.sleep(0)  # flush
        snap = engine.snapshot()
        assert snap.metrics.captures_attempted >= 1
