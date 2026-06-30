import os

import pytest
from fastapi import FastAPI


def test_asgi_app_exposes_fastapi_instance(monkeypatch: pytest.MonkeyPatch) -> None:
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
    routes = {getattr(r, "path", None) for r in asgi.app.routes}
    assert "/api/health" in routes
