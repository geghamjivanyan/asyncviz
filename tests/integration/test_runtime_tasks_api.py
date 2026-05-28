from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from asyncviz.runtime.tasks import TaskMetadata


def test_list_tasks_empty(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/api/runtime/tasks")
        assert response.status_code == 200
        body = response.json()
        assert body["tasks"] == []
        assert body["total"] == 0
        assert body["active"] == 0


def test_list_tasks_returns_seeded_snapshot(app: FastAPI) -> None:
    registry = app.state.task_registry
    registry.register("t1", metadata=TaskMetadata(coroutine_name="worker"))
    registry.register("t2", metadata=TaskMetadata(coroutine_name="other"))

    with TestClient(app) as client:
        response = client.get("/api/runtime/tasks")
        assert response.status_code == 200
        body = response.json()
        ids = [t["task_id"] for t in body["tasks"]]
        # Lifespan exit clears the registry, but the snapshot is taken during
        # the `with` block — so we should see both seeded tasks plus whatever
        # the lifespan added (heartbeat task on the dashboard's loop).
        assert "t1" in ids
        assert "t2" in ids


def test_list_tasks_active_only_filters_terminal(app: FastAPI) -> None:
    registry = app.state.task_registry
    registry.register("active")
    registry.register("done")
    from asyncviz.runtime.events.models.enums import TaskState

    registry.update_state("done", TaskState.COMPLETED)

    with TestClient(app) as client:
        response = client.get("/api/runtime/tasks?active_only=true")
        assert response.status_code == 200
        ids = {t["task_id"] for t in response.json()["tasks"]}
        assert "active" in ids
        assert "done" not in ids


def test_get_single_task_returns_snapshot(app: FastAPI) -> None:
    registry = app.state.task_registry
    registry.register("solo", metadata=TaskMetadata(coroutine_name="my_coro"))

    with TestClient(app) as client:
        response = client.get("/api/runtime/tasks/solo")
        assert response.status_code == 200
        body = response.json()
        assert body["task_id"] == "solo"
        assert body["coroutine_name"] == "my_coro"
        assert body["state"] == "created"


def test_get_unknown_task_returns_404(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/api/runtime/tasks/ghost")
        assert response.status_code == 404
        assert "ghost" in response.json()["detail"]
