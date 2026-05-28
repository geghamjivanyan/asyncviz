from fastapi import FastAPI
from fastapi.testclient import TestClient

from asyncviz.dashboard.websocket.protocol import PROTOCOL_VERSION


def test_runtime_status_returns_typed_payload(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/api/runtime/status")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "running"
        assert body["protocol_version"] == PROTOCOL_VERSION
        assert body["connected_clients"] == 0
        assert body["uptime_seconds"] >= 0.0


def test_runtime_metrics_returns_snapshot(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/api/runtime/metrics")
        assert response.status_code == 200
        body = response.json()
        assert body["events_emitted"] == 0
        assert body["websocket_messages_sent"] == 0
