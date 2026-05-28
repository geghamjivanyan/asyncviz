import json

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok(app: FastAPI) -> None:
    # /api/health now returns the canonical HealthSnapshot. Inside the
    # TestClient lifespan every default probe is HEALTHY, so the
    # aggregated status is "healthy". The body is no longer
    # ``{"status": "ok"}`` — this regression test enforces the new
    # protocol shape.
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert isinstance(body["checks"], list) and body["checks"]
    assert body["summary"]["checks_total"] == len(body["checks"])


def test_websocket_route_accepts_and_closes(app: FastAPI) -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        # On connect, the server sends an initial runtime_snapshot frame.
        env = json.loads(ws.receive_text())
        assert env["type"] == "runtime_snapshot"
