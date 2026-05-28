import pytest
from fastapi import FastAPI


def test_asgi_app_exposes_fastapi_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("ASYNCVIZ_HOST", "ASYNCVIZ_PORT", "ASYNCVIZ_OPEN_BROWSER", "ASYNCVIZ_DEBUG"):
        monkeypatch.delenv(key, raising=False)

    import importlib

    import asyncviz.dashboard.asgi as asgi

    importlib.reload(asgi)

    assert isinstance(asgi.app, FastAPI)
    routes = {getattr(r, "path", None) for r in asgi.app.routes}
    assert "/api/health" in routes
