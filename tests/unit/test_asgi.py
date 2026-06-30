import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_asgi_app_exposes_fastapi_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ASGI entry point must expose a working FastAPI app whose
    canonical health endpoint actually responds.

    The health route is registered in :mod:`asyncviz.dashboard.routes.health`
    as ``/health`` and mounted under the ``/api`` prefix by
    :func:`asyncviz.dashboard.create_app`, so a GET to ``/api/health``
    must succeed against the app constructed in
    :mod:`asyncviz.dashboard.asgi`.

    The test runs an actual request through the app rather than
    introspecting ``app.routes`` directly. ``app.routes`` is a
    structural view that can surface paths differently across
    Starlette / FastAPI releases (``Mount`` vs ``APIRoute``,
    sub-app delegation, etc.), and the contract that matters for an
    operator running ``uvicorn asyncviz.dashboard.asgi:app`` is that
    the endpoint responds — not how the route happens to be encoded
    in the in-memory route list.
    """
    # Clear *every* ASYNCVIZ_* env var so the module-level
    # ``create_app(AsyncVizConfig.from_env())`` always sees the
    # documented defaults — CI runners (GitHub Actions in particular)
    # occasionally leak values such as ``ASYNCVIZ_FRONTEND_MODE`` that
    # would otherwise change the constructed app's routing.
    for key in list(os.environ):
        if key.startswith("ASYNCVIZ_"):
            monkeypatch.delenv(key, raising=False)

    import importlib

    import asyncviz.dashboard.asgi as asgi

    importlib.reload(asgi)

    assert isinstance(asgi.app, FastAPI)

    # Drive the live endpoint. ``TestClient`` runs the actual ASGI
    # routing pipeline, so this is the strongest possible assertion
    # that ``/api/health`` is wired up correctly.
    with TestClient(asgi.app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200, (
        f"/api/health returned HTTP {response.status_code}; "
        f"registered paths: "
        f"{sorted(p for p in (getattr(r, 'path', None) for r in asgi.app.routes) if p)!r}"
    )
