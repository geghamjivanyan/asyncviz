from __future__ import annotations

import json

from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app
from asyncviz.dashboard.websocket.protocol import PROTOCOL_VERSION


def _fast_heartbeat_app():
    return create_app(AsyncVizConfig(open_browser=False, heartbeat_interval=0.05))


def _receive_envelope(ws) -> dict:
    return json.loads(ws.receive_text())


def _consume_until(ws, message_type: str, *, max_frames: int = 20) -> dict:
    """Read frames until one of ``message_type`` arrives, ignoring others."""
    for _ in range(max_frames):
        env = _receive_envelope(ws)
        if env["type"] == message_type:
            return env
    msg = f"never saw envelope.type == {message_type!r}"
    raise AssertionError(msg)


def test_websocket_sends_snapshot_on_connect() -> None:
    app = create_app(
        AsyncVizConfig(
            open_browser=False,
            heartbeat_interval=60.0,
            enable_instrumentation=False,
        )
    )
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        env = _receive_envelope(ws)
        assert env["type"] == "runtime_snapshot"
        assert env["protocol_version"] == PROTOCOL_VERSION
        assert env["payload"]["last_sequence"] == 0
        assert env["payload"]["tasks"] == []
        assert "metrics" in env["payload"]


def test_websocket_receives_heartbeat() -> None:
    app = _fast_heartbeat_app()
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        # First frame is the on-connect snapshot; drain it.
        _consume_until(ws, "runtime_snapshot")
        # Then wait for a heartbeat.
        env = _consume_until(ws, "heartbeat")
        assert env["protocol_version"] == PROTOCOL_VERSION
        assert env["payload"]["connected_clients"] >= 1
        assert env["payload"]["server_uptime_seconds"] >= 0


def test_websocket_disconnect_is_clean() -> None:
    app = _fast_heartbeat_app()
    with TestClient(app) as client:
        manager = app.state.websocket_manager
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()  # ensure connection is registered
            assert manager.client_count == 1
        import time

        deadline = time.monotonic() + 1.0
        while manager.client_count > 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert manager.client_count == 0


def test_multiple_clients_each_receive_heartbeat() -> None:
    app = _fast_heartbeat_app()
    with (
        TestClient(app) as client,
        client.websocket_connect("/ws") as ws_a,
        client.websocket_connect("/ws") as ws_b,
    ):
        for ws in (ws_a, ws_b):
            env = _consume_until(ws, "heartbeat")
            assert env["type"] == "heartbeat"
