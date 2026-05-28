from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asyncviz.runtime.tasks import TaskRegistry


def test_task_registry_is_attached_to_app(app: FastAPI) -> None:
    assert isinstance(app.state.task_registry, TaskRegistry)


def test_task_registry_starts_and_stops_with_lifespan(app: FastAPI) -> None:
    registry: TaskRegistry = app.state.task_registry
    registry.register("baseline")
    assert len(registry) == 1

    with TestClient(app) as client:
        # API still works while the registry is up.
        assert client.get("/api/health").status_code == 200

        registry.register("during-lifespan")
        assert len(registry) == 2

    # Lifespan exit clears the registry (via TaskRegistry.stop()).
    assert len(registry) == 0


def test_task_registry_is_per_app_instance() -> None:
    from asyncviz.config import AsyncVizConfig
    from asyncviz.dashboard import create_app

    a = create_app(AsyncVizConfig(open_browser=False, heartbeat_interval=60.0))
    b = create_app(AsyncVizConfig(open_browser=False, heartbeat_interval=60.0))
    assert a.state.task_registry is not b.state.task_registry
