from __future__ import annotations

from fastapi.testclient import TestClient

from asyncviz.dashboard import create_app
from asyncviz.dashboard.assets import (
    build_asset_diagnostics,
    clear_asset_trace,
    record_asset_trace,
    reset_asset_metrics,
    reset_resolution_cache,
    set_asset_trace_enabled,
)


def setup_function(_fn: object) -> None:
    reset_asset_metrics()
    clear_asset_trace()
    set_asset_trace_enabled(False)
    reset_resolution_cache()


def test_build_asset_diagnostics_emits_full_snapshot() -> None:
    snap = build_asset_diagnostics()
    payload = snap.to_dict()
    assert "bundle" in payload
    assert "validation" in payload
    assert "metrics" in payload
    assert payload["trace_enabled"] is False


def test_trace_ring_records_events_when_enabled() -> None:
    set_asset_trace_enabled(True)
    record_asset_trace("publish-start", "x")
    record_asset_trace("publish-finished", "y")
    snap = build_asset_diagnostics()
    kinds = [entry.kind for entry in snap.recent_trace]
    assert "publish-start" in kinds
    assert "publish-finished" in kinds


def test_trace_ring_silent_when_disabled() -> None:
    record_asset_trace("publish-start", "x")
    snap = build_asset_diagnostics()
    assert snap.recent_trace == ()


def test_assets_endpoint_returns_diagnostics() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/assets")
    assert response.status_code == 200
    body = response.json()
    assert "bundle" in body
    assert "manifest" in body
    assert "validation" in body
    assert body["validation"]["ok"] in {True, False}


def test_assets_endpoint_in_openapi_schema() -> None:
    app = create_app()
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "/api/assets" in schema["paths"]
