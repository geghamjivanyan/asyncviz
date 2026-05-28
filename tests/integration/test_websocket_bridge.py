from __future__ import annotations

import json

from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app
from asyncviz.dashboard.websocket.protocol import PROTOCOL_VERSION
from asyncviz.runtime.events.models import TaskCreatedEvent, TaskFailedEvent


def _make_app() -> object:
    return create_app(
        AsyncVizConfig(
            open_browser=False,
            heartbeat_interval=60.0,
            enable_instrumentation=False,
        )
    )


def _drain_snapshot(ws) -> dict:
    env = json.loads(ws.receive_text())
    assert env["type"] == "runtime_snapshot"
    return env


def _receive_envelope_of(ws, kind: str) -> dict:
    """Pull frames off ``ws`` until one of type ``kind`` arrives.

    The streaming engine now interleaves ``metrics_delta`` / ``timeline_delta``
    envelopes alongside the bridge's ``runtime_event`` frames. Tests that
    target a specific envelope kind use this helper to skip the others.
    """
    while True:
        env = json.loads(ws.receive_text())
        if env["type"] == kind:
            return env


def test_bridge_forwards_events_to_websocket() -> None:
    app = _make_app()
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        _drain_snapshot(ws)
        bus = app.state.event_bus
        bus.publish(TaskCreatedEvent(task_id="t1", coroutine_name="worker"))

        envelope = _receive_envelope_of(ws, "runtime_event")
        assert envelope["protocol_version"] == PROTOCOL_VERSION
        assert envelope["sequence"] == 1
        assert envelope["payload"]["event_type"] == "asyncio.task.created"
        assert envelope["payload"]["task_id"] == "t1"
        assert envelope["payload"]["coroutine_name"] == "worker"


def test_bridge_carries_terminal_events_too() -> None:
    app = _make_app()
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        _drain_snapshot(ws)
        bus = app.state.event_bus
        bus.publish(
            TaskFailedEvent(
                task_id="t1",
                exception_type="RuntimeError",
                exception_message="boom",
                duration_seconds=0.5,
                created_at=100.0,
                completed_at=100.5,
            )
        )
        envelope = _receive_envelope_of(ws, "runtime_event")
        assert envelope["payload"]["event_type"] == "asyncio.task.failed"
        assert envelope["payload"]["exception_type"] == "RuntimeError"
        assert envelope["payload"]["exception_message"] == "boom"
        assert envelope["payload"]["created_at"] == 100.0
        assert envelope["payload"]["completed_at"] == 100.5


def test_bridge_metrics_increment_on_broadcast() -> None:
    app = _make_app()
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        _drain_snapshot(ws)
        bus = app.state.event_bus
        bridge = app.state.websocket_bridge

        bus.publish(TaskCreatedEvent(task_id="t1"))
        bus.publish(TaskCreatedEvent(task_id="t2"))

        import time

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and bridge.metrics.forwarded < 2:
            time.sleep(0.02)

        assert bridge.metrics.forwarded >= 2
        assert bridge.metrics.dropped == 0
        assert bridge.metrics.serialization_failures == 0
        assert bridge.metrics.snapshots_emitted == 1


def test_bridge_unsubscribes_on_lifespan_exit() -> None:
    app = _make_app()
    bridge = None
    with TestClient(app):
        bridge = app.state.websocket_bridge
        assert bridge.is_running

    assert bridge is not None
    assert not bridge.is_running


def test_multiple_clients_each_receive_runtime_events() -> None:
    app = _make_app()
    with (
        TestClient(app) as client,
        client.websocket_connect("/ws") as ws_a,
        client.websocket_connect("/ws") as ws_b,
    ):
        _drain_snapshot(ws_a)
        _drain_snapshot(ws_b)
        app.state.event_bus.publish(TaskCreatedEvent(task_id="t1"))

        envelopes = [
            _receive_envelope_of(ws_a, "runtime_event"),
            _receive_envelope_of(ws_b, "runtime_event"),
        ]
        for env in envelopes:
            assert env["payload"]["task_id"] == "t1"


def test_sequence_increments_monotonically() -> None:
    app = _make_app()
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        _drain_snapshot(ws)
        bus = app.state.event_bus
        for i in range(5):
            bus.publish(TaskCreatedEvent(task_id=f"t{i}"))

        # The streaming engine fans out ``metrics_delta`` envelopes alongside
        # the bridge's ``runtime_event`` envelopes — filter for the bridge's
        # frames specifically and assert their sequence ordering.
        seqs: list[int] = []
        while len(seqs) < 5:
            env = json.loads(ws.receive_text())
            if env["type"] != "runtime_event":
                continue
            seqs.append(env["sequence"])
        assert seqs == [1, 2, 3, 4, 5]


def test_snapshot_includes_existing_tasks() -> None:
    app = _make_app()
    registry = app.state.task_registry
    registry.register("preexisting")

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        env = _drain_snapshot(ws)
        task_ids = {t["task_id"] for t in env["payload"]["tasks"]}
        assert "preexisting" in task_ids


def test_health_websocket_route_consumes_snapshot_then_closes() -> None:
    app = _make_app()
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        env = _drain_snapshot(ws)
        assert env["payload"]["last_sequence"] == 0
