from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import app as app_module, create_app


def _make_app_with_static(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    (tmp_path / "index.html").write_text("<!doctype html><title>asyncviz</title>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-abc123.js").write_text("console.log('hello');\n")
    (assets / "index-abc123.css").write_text("body{background:#000;}\n")
    (tmp_path / "favicon.ico").write_bytes(b"\x00\x00")

    monkeypatch.setattr(app_module, "STATIC_DIR", tmp_path)
    return create_app(AsyncVizConfig(open_browser=False, heartbeat_interval=60.0))


def test_health_works_without_frontend_bundle(app: FastAPI) -> None:
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200


def test_frontend_bundle_is_served_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _make_app_with_static(tmp_path, monkeypatch)
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "asyncviz" in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_spa_fallback_returns_index_for_unknown_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _make_app_with_static(tmp_path, monkeypatch)
    client = TestClient(app)
    response = client.get("/some/deep/route")

    assert response.status_code == 200
    assert "asyncviz" in response.text


def test_api_routes_not_shadowed_by_spa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_static(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    # /api/health now returns the canonical HealthSnapshot — the regression
    # this test guards (SPA fallback shadowing the API) is verified by the
    # presence of the structured body.
    body = response.json()
    assert "status" in body
    assert "checks" in body


def test_bare_health_route_is_not_shadowed_by_spa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression for the canonical SPA-fallback bug: a request to the
    # un-prefixed ``/health`` path used to be served the React shell
    # with HTTP 200, which the SPA router then rendered as
    # "Unexpected Application Error! 404 Not Found". The catch-all
    # must now treat ``/health`` as reserved and return an HTTP 404
    # (because no backend route is registered at the bare /health in
    # this app) rather than leak the SPA shell.
    app = _make_app_with_static(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 404
    # Critically — the response body must NOT be the SPA's index.html.
    assert "<!doctype html" not in response.text.lower()
    assert "asyncviz</title>" not in response.text


def test_docs_route_is_not_shadowed_by_spa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_static(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.get("/docs")
    # FastAPI's auto-mounted Swagger UI serves the docs HTML — but the
    # critical assertion is that it is NOT the SPA shell.
    assert response.status_code == 200
    assert "asyncviz</title>" not in response.text
    assert "swagger" in response.text.lower()


def test_openapi_schema_is_not_shadowed_by_spa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _make_app_with_static(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["title"] == "AsyncViz"


def test_websocket_route_is_not_shadowed_by_spa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The websocket upgrade path must reach the websocket router, not
    # the SPA catch-all. A GET against /ws would otherwise have been
    # answered with index.html under the buggy fallback; with the fix
    # it must hit the websocket route (which rejects non-upgrade GETs
    # with a 4xx, never with the SPA shell).
    app = _make_app_with_static(tmp_path, monkeypatch)
    with TestClient(app) as client:
        # A plain GET on a websocket endpoint returns a non-2xx;
        # what matters is that the body is not the SPA shell.
        response = client.get("/ws")
    assert response.status_code in {400, 404, 405, 426}
    assert "asyncviz</title>" not in response.text


def test_spa_routes_are_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Hard-refresh on canonical SPA deep-links must continue to serve
    # the React shell so React Router can take over on hydration.
    app = _make_app_with_static(tmp_path, monkeypatch)
    with TestClient(app) as client:
        for spa_route in (
            "/",
            "/timeline",
            "/metrics",
            "/warnings",
            "/replay",
            "/replay/abc-123",
            "/diagnostics",
            "/diagnostics/queues/foo",
        ):
            response = client.get(spa_route)
            assert response.status_code == 200, spa_route
            assert "asyncviz" in response.text, spa_route
            assert response.headers["cache-control"] == "no-cache", spa_route


def test_paths_that_resemble_reserved_prefixes_still_serve_spa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Boundary-safety regression: a SPA route whose name happens to
    # start with the same characters as a reserved prefix
    # (``/api-keys-page``, ``/healthz-info``) must NOT be 404'd by the
    # reserved-prefix gate — those are real frontend deep-links.
    app = _make_app_with_static(tmp_path, monkeypatch)
    with TestClient(app) as client:
        for spa_route in ("/api-keys-page", "/apiary", "/healthz-info", "/wsdebug"):
            response = client.get(spa_route)
            assert response.status_code == 200, spa_route
            assert "asyncviz" in response.text, spa_route


def test_hashed_assets_have_immutable_cache_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _make_app_with_static(tmp_path, monkeypatch)
    client = TestClient(app)

    js = client.get("/assets/index-abc123.js")
    assert js.status_code == 200
    assert js.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert js.headers["content-type"].startswith("application/javascript") or js.headers[
        "content-type"
    ].startswith("text/javascript")

    css = client.get("/assets/index-abc123.css")
    assert css.status_code == 200
    assert css.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert css.headers["content-type"].startswith("text/css")


def test_loose_assets_get_short_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_static(tmp_path, monkeypatch)
    client = TestClient(app)

    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=3600"


def test_path_traversal_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _make_app_with_static(tmp_path, monkeypatch)
    client = TestClient(app)

    # Starlette normalizes /../etc before our handler sees it. Confirm at minimum
    # that an absolute-ish escape returns 4xx, never 200 with leaked content.
    response = client.get("/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code in {404, 400}


def test_static_dir_resolves_inside_package() -> None:
    assert app_module.STATIC_DIR.name == "static"
    assert app_module.STATIC_DIR.parent.name == "dashboard"
    assert app_module.STATIC_DIR.parent.parent.name == "asyncviz"
