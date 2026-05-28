from __future__ import annotations

import json

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app
from asyncviz.dashboard.exceptions import (
    ConflictError,
    NotFoundError,
    ReplayWindowMissError,
    UnavailableError,
    ValidationError,
    error_response_payload,
)
from asyncviz.dashboard.middleware.correlation import (
    CORRELATION_HEADER,
    current_correlation_id,
)
from asyncviz.dashboard.middleware.timing import TIMING_HEADER
from asyncviz.dashboard.state.backend import BackendAppState
from asyncviz.dashboard.state.backend_metrics import BackendMetrics


@pytest.fixture
def app():
    # ``frontend_mode='api-only'`` keeps the SPA fallback from shadowing
    # dynamically-added test routes (which all live under ``/api/_test*``).
    return create_app(AsyncVizConfig(frontend_mode="api-only"))


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


# ── BackendMetrics primitives ─────────────────────────────────────────────


def test_backend_metrics_records_request_lifecycle() -> None:
    metrics = BackendMetrics()
    metrics.begin_request()
    metrics.record_request(method="GET", path="/api/foo", status_code=200, duration_ms=12.3)
    metrics.end_request()
    snap = metrics.snapshot()
    assert snap.requests_total == 1
    assert snap.requests_in_flight == 0
    assert snap.requests_by_method["GET"] == 1
    assert snap.requests_by_status["200"] == 1
    assert snap.average_duration_ms == pytest.approx(12.3)


def test_backend_metrics_tracks_max_duration() -> None:
    metrics = BackendMetrics()
    for duration in (5.0, 12.0, 8.0, 22.5):
        metrics.record_request(method="GET", path="/x", status_code=200, duration_ms=duration)
    snap = metrics.snapshot()
    assert snap.max_duration_ms == pytest.approx(22.5)


def test_backend_metrics_records_errors_by_code() -> None:
    metrics = BackendMetrics()
    metrics.record_api_error("not_found")
    metrics.record_api_error("not_found")
    metrics.record_api_error("validation_error")
    snap = metrics.snapshot()
    assert snap.api_errors_total == 3
    assert snap.api_errors_by_code["not_found"] == 2


def test_backend_metrics_websocket_lifecycle() -> None:
    metrics = BackendMetrics()
    metrics.record_ws_connect()
    metrics.record_ws_connect()
    metrics.record_ws_disconnect()
    assert metrics.active_ws_connections() == 1
    snap = metrics.snapshot()
    assert snap.ws_active_connections == 1


def test_backend_metrics_reset_clears() -> None:
    metrics = BackendMetrics()
    metrics.record_request(method="GET", path="/x", status_code=200, duration_ms=1.0)
    metrics.reset()
    snap = metrics.snapshot()
    assert snap.requests_total == 0


# ── Typed BackendAppState ─────────────────────────────────────────────────


def test_create_app_attaches_typed_backend_state(app) -> None:
    backend = app.state.backend
    assert isinstance(backend, BackendAppState)
    # All service refs present and non-None.
    assert backend.runtime_clock is not None
    assert backend.state_store is not None
    assert backend.timeline_engine is not None
    assert backend.metrics_aggregator is not None
    assert backend.warning_manager is not None
    assert backend.replay_buffer is not None
    assert backend.metrics is not None


def test_legacy_app_state_references_still_present(app) -> None:
    # Backward compat: the old ``app.state.X`` references are still set
    # alongside the typed container.
    assert app.state.runtime_clock is app.state.backend.runtime_clock
    assert app.state.state_store is app.state.backend.state_store


# ── Middleware behavior ───────────────────────────────────────────────────


def test_correlation_id_is_stamped_on_responses(client) -> None:
    response = client.get("/api/runtime/status")
    assert response.status_code == 200
    assert CORRELATION_HEADER in response.headers
    # uuid4 hex is 32 chars; we accept any non-empty string.
    assert response.headers[CORRELATION_HEADER]


def test_correlation_id_preserves_inbound_value(client) -> None:
    response = client.get(
        "/api/runtime/status",
        headers={CORRELATION_HEADER: "inbound-id-12345"},
    )
    assert response.headers[CORRELATION_HEADER] == "inbound-id-12345"


def test_response_time_header_present(client) -> None:
    response = client.get("/api/runtime/status")
    assert TIMING_HEADER in response.headers
    # The value should be parseable as a float.
    float(response.headers[TIMING_HEADER])


def test_request_metrics_increment_on_call(client, app) -> None:
    before = app.state.backend.metrics.snapshot().requests_total
    client.get("/api/runtime/status")
    client.get("/api/runtime/status")
    after = app.state.backend.metrics.snapshot().requests_total
    assert after - before == 2


def test_static_assets_skip_request_metrics(client, app) -> None:
    # Hitting a non-existent asset would still flow through the middleware,
    # but `/assets/` paths are excluded from the counter.
    before = app.state.backend.metrics.snapshot().requests_total
    client.get("/assets/does-not-exist.css")
    after = app.state.backend.metrics.snapshot().requests_total
    assert after == before


# ── Backend metrics endpoint ──────────────────────────────────────────────


def test_backend_metrics_endpoint_returns_canonical_shape(client) -> None:
    # Touch a couple of endpoints first so the counters aren't empty.
    client.get("/api/runtime/status")
    client.get("/api/runtime/clock")
    response = client.get("/api/runtime/backend")
    assert response.status_code == 200
    data = response.json()
    assert data["requests_total"] >= 2
    assert data["api_errors_total"] == 0
    assert "GET" in data["requests_by_method"]
    assert "200" in data["requests_by_status"]
    assert data["average_duration_ms"] >= 0.0


# ── Typed API errors / handlers ───────────────────────────────────────────


def test_api_error_subclasses_carry_codes_and_status() -> None:
    cases = [
        (NotFoundError, "not_found", 404),
        (ConflictError, "conflict", 409),
        (ValidationError, "validation_error", 422),
        (UnavailableError, "service_unavailable", 503),
        (ReplayWindowMissError, "replay_window_miss", 409),
    ]
    for cls, code, status in cases:
        err = cls("oops", details={"why": "test"})
        assert err.code == code
        assert err.status_code == status
        assert err.details["why"] == "test"


def test_error_response_payload_shape() -> None:
    payload = error_response_payload(
        code="not_found",
        message="missing",
        status_code=404,
        details={"id": "abc"},
        correlation_id="cid-1",
    )
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["status_code"] == 404
    assert payload["error"]["details"]["id"] == "abc"
    assert payload["error"]["correlation_id"] == "cid-1"
    json.dumps(payload)  # JSON-safe


def test_unhandled_exception_normalized_by_middleware(client, app) -> None:
    """Inject a route that raises and confirm the middleware envelopes it."""
    test_router = APIRouter()

    @test_router.get("/raises")
    async def raises_unhandled() -> dict:
        raise RuntimeError("kaboom")

    @test_router.get("/raises-typed")
    async def raises_typed() -> dict:
        raise NotFoundError("nope", details={"id": "z"})

    app.include_router(test_router, prefix="/api/_test")

    r1 = client.get("/api/_test/raises")
    assert r1.status_code == 500
    body = r1.json()
    assert body["error"]["code"] == "internal_server_error"
    assert body["error"]["status_code"] == 500
    assert body["error"]["correlation_id"]

    r2 = client.get("/api/_test/raises-typed")
    assert r2.status_code == 404
    body = r2.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["details"]["id"] == "z"

    # API errors get counted on the backend metrics.
    snap = app.state.backend.metrics.snapshot()
    assert snap.api_errors_by_code.get("not_found", 0) >= 1
    assert snap.api_errors_by_code.get("internal_server_error", 0) >= 1


def test_correlation_id_threaded_through_error_envelope(client, app) -> None:
    test_router = APIRouter()

    @test_router.get("/raises")
    async def raises_typed() -> dict:
        raise NotFoundError("nope")

    app.include_router(test_router, prefix="/api/_test2")

    response = client.get(
        "/api/_test2/raises",
        headers={CORRELATION_HEADER: "trace-zzz"},
    )
    assert response.headers[CORRELATION_HEADER] == "trace-zzz"
    body = response.json()
    assert body["error"]["correlation_id"] == "trace-zzz"


# ── Backend reachable from inside handlers ────────────────────────────────


def test_handlers_can_resolve_typed_backend_state(client, app) -> None:
    from fastapi import Depends

    from asyncviz.dashboard.dependencies import get_backend_state

    test_router = APIRouter()

    @test_router.get("/backend-resolved")
    async def backend_resolved(backend=Depends(get_backend_state)):
        return {"has_state_store": backend.state_store is not None}

    app.include_router(test_router, prefix="/api/_test3")

    response = client.get("/api/_test3/backend-resolved")
    assert response.status_code == 200
    assert response.json()["has_state_store"] is True


# ── current_correlation_id() inside a handler ────────────────────────────


def test_current_correlation_id_returns_active_request_id(client, app) -> None:
    test_router = APIRouter()

    @test_router.get("/cid")
    async def cid_handler() -> dict:
        return {"cid": current_correlation_id()}

    app.include_router(test_router, prefix="/api/_test4")

    response = client.get(
        "/api/_test4/cid",
        headers={CORRELATION_HEADER: "explicit-id"},
    )
    assert response.json()["cid"] == "explicit-id"


# ── BackendAppState fields ────────────────────────────────────────────────


def test_backend_state_extras_is_writable_dict(app) -> None:
    backend = app.state.backend
    backend.extras["test"] = 42
    assert backend.extras["test"] == 42
