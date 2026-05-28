from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI

import asyncviz
from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app


@pytest.fixture
def config() -> AsyncVizConfig:
    return AsyncVizConfig(
        host="127.0.0.1",
        port=8911,
        open_browser=False,
        debug=False,
        heartbeat_interval=60.0,
        enable_instrumentation=False,
    )


@pytest.fixture
def app(config: AsyncVizConfig) -> FastAPI:
    return create_app(config)


@pytest.fixture(autouse=True)
def _reset_runtime() -> Iterator[None]:
    """Ensure no AsyncViz runtime survives between tests."""
    yield
    if asyncviz.is_running():
        asyncviz.stop()
