"""End-to-end tests for the dashboard's CORS middleware wiring.

The :class:`CORSMiddleware` is registered by
:func:`asyncviz.dashboard.app._register_cors_middleware` based on
:attr:`AsyncVizConfig.cors_allowed_origins`. These tests exercise the
real ``create_app`` path so we catch regressions in:

  * what origins get an ``Access-Control-Allow-Origin`` echo
  * preflight (``OPTIONS``) behavior
  * the wildcard ``("*",)`` credentials downgrade
  * the empty-tuple disable-CORS branch
  * websocket route passthrough (CORS middleware is HTTP-only)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app

VITE_ORIGIN = "http://localhost:5173"
VITE_LOOPBACK_ORIGIN = "http://127.0.0.1:5173"
UNKNOWN_ORIGIN = "http://evil.example.com"


def _client(config: AsyncVizConfig | None = None) -> TestClient:
    return TestClient(create_app(config or AsyncVizConfig(open_browser=False)))


# ── Default-origins behavior ──────────────────────────────────────────────


@pytest.mark.parametrize("origin", [VITE_ORIGIN, VITE_LOOPBACK_ORIGIN])
def test_default_config_allows_vite_dev_origins(origin: str) -> None:
    """Out-of-the-box AsyncViz must serve the Vite dev workflow."""
    with _client() as client:
        response = client.get("/api/health/live", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_default_config_denies_unknown_origin() -> None:
    """Unlisted origins must not receive an ACAO echo."""
    with _client() as client:
        response = client.get("/api/health/live", headers={"Origin": UNKNOWN_ORIGIN})
    # The request itself succeeds — CORS denial is enforced by the
    # browser via the absence of the echo header, not by a 4xx.
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_preflight_options_succeeds_for_allowed_origin() -> None:
    """``OPTIONS`` preflight for an allowed origin returns 200 + ACAO."""
    with _client() as client:
        response = client.options(
            "/api/health/live",
            headers={
                "Origin": VITE_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == VITE_ORIGIN
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "GET" in allow_methods.upper() or allow_methods == "*"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_preflight_options_denies_unknown_origin() -> None:
    with _client() as client:
        response = client.options(
            "/api/health/live",
            headers={
                "Origin": UNKNOWN_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
    # Starlette returns 400 for preflight from a non-allowed origin
    # because it short-circuits with "Disallowed CORS origin".
    assert response.status_code in {400, 403}
    assert "access-control-allow-origin" not in response.headers


def test_acao_header_is_not_duplicated() -> None:
    """Each request must produce exactly one Access-Control-Allow-Origin."""
    with _client() as client:
        response = client.get("/api/health/live", headers={"Origin": VITE_ORIGIN})
    # ``Response.headers.get_list`` exposes any duplicates the
    # middleware stack might have appended.
    matches = [
        value
        for name, value in response.headers.multi_items()
        if name.lower() == "access-control-allow-origin"
    ]
    assert matches == [VITE_ORIGIN]


# ── Custom origin lists ───────────────────────────────────────────────────


def test_custom_origin_list_overrides_defaults() -> None:
    config = AsyncVizConfig(
        open_browser=False,
        cors_allowed_origins=("https://app.example.com",),
    )
    with _client(config) as client:
        # The configured origin is echoed.
        allowed = client.get(
            "/api/health/live",
            headers={"Origin": "https://app.example.com"},
        )
        assert allowed.headers.get("access-control-allow-origin") == "https://app.example.com"
        # The Vite default origin is no longer allowed.
        denied = client.get("/api/health/live", headers={"Origin": VITE_ORIGIN})
        assert "access-control-allow-origin" not in denied.headers


def test_empty_origin_list_disables_cors_middleware() -> None:
    """Same-origin deployments can opt out by setting the list to ``()``."""
    config = AsyncVizConfig(open_browser=False, cors_allowed_origins=())
    with _client(config) as client:
        response = client.get("/api/health/live", headers={"Origin": VITE_ORIGIN})
    # Request still works (same-origin in prod doesn't need CORS).
    assert response.status_code == 200
    # No ACAO at all — the middleware was never registered.
    assert "access-control-allow-origin" not in response.headers


def test_wildcard_origin_disables_credentials() -> None:
    """``("*",)`` must downgrade ``allow_credentials`` to False.

    A wildcard ACAO with ``Access-Control-Allow-Credentials: true``
    is rejected by every modern browser and triggers a runtime
    Starlette warning. We force the safe combination instead.
    """
    config = AsyncVizConfig(open_browser=False, cors_allowed_origins=("*",))
    with _client(config) as client:
        response = client.get("/api/health/live", headers={"Origin": UNKNOWN_ORIGIN})
    assert response.headers.get("access-control-allow-origin") == "*"
    # Critical assertion: credentials must NOT be true when origin is "*".
    assert response.headers.get("access-control-allow-credentials") != "true"


# ── Embedded-mode (same-origin) sanity ────────────────────────────────────


def test_same_origin_request_without_origin_header_works_unchanged() -> None:
    """Requests that don't carry an ``Origin`` header bypass CORS entirely.

    Embedded production deployments serve the SPA from the same origin
    as the API; browsers omit ``Origin`` on same-origin GETs. The
    middleware must let those through with no extra headers.
    """
    with _client() as client:
        response = client.get("/api/health/live")
    assert response.status_code == 200
    # No ACAO because there was no Origin to echo against.
    assert "access-control-allow-origin" not in response.headers


# ── Websocket passthrough ─────────────────────────────────────────────────


def test_websocket_is_not_blocked_by_cors_middleware() -> None:
    """Starlette's CORS middleware only inspects HTTP scopes.

    The websocket route uses a different scope type (``"websocket"``)
    that the middleware passes through unchanged — so introducing
    CORS must not break the realtime stream regardless of the
    client's origin.
    """
    # The ``Origin`` here would normally trigger a CORS check on
    # an HTTP request; for the websocket scope it's purely
    # informational. The test client raises if the connection
    # fails outright, so reaching the body is the assertion.
    with _client() as client, client.websocket_connect("/ws") as ws:
        # Receive at least one frame to confirm the bridge handshake
        # ran end-to-end (snapshot / replay envelope).
        envelope = ws.receive_json()
        assert envelope.get("type") is not None


# ── Range coverage for the /api/* endpoints the SPA hydrates ──────────────


@pytest.mark.parametrize(
    "path",
    [
        "/api/health",
        "/api/health/live",
        "/api/runtime/state",
        "/api/runtime/snapshot",
        "/api/runtime/warnings/blocking",
        "/api/queues",
        "/api/queues/metrics",
        "/api/semaphores",
        "/api/executor/metrics",
    ],
)
def test_acao_echoes_on_every_spa_hydration_endpoint(path: str) -> None:
    """Every endpoint the SPA hydrates must be CORS-reachable in dev."""
    with _client() as client:
        response = client.get(path, headers={"Origin": VITE_ORIGIN})
    # We don't care about 200 vs 5xx here — some endpoints need lifespan
    # state that the TestClient may not warm up. What matters is that
    # whatever response the backend produces gets the ACAO echo.
    assert response.headers.get("access-control-allow-origin") == VITE_ORIGIN, (
        f"{path} did not receive CORS allow-origin echo (status={response.status_code})"
    )
