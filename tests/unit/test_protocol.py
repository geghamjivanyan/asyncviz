import json

from asyncviz.dashboard.websocket.protocol import (
    PROTOCOL_VERSION,
    Envelope,
    heartbeat,
    system_status,
)


def test_heartbeat_envelope_shape() -> None:
    envelope = heartbeat(uptime_seconds=3.5, connected_clients=2)
    assert envelope.type == "heartbeat"
    assert envelope.protocol_version == PROTOCOL_VERSION
    assert envelope.timestamp > 0
    assert envelope.payload["server_uptime_seconds"] == 3.5
    assert envelope.payload["connected_clients"] == 2


def test_envelope_serializes_to_json() -> None:
    envelope = heartbeat(uptime_seconds=1.0, connected_clients=0)
    data = json.loads(envelope.model_dump_json())
    assert data["protocol_version"] == PROTOCOL_VERSION
    assert data["type"] == "heartbeat"
    assert "timestamp" in data
    assert "payload" in data


def test_system_status_envelope() -> None:
    envelope = system_status("running", debug=True)
    assert envelope.type == "system_status"
    assert envelope.payload["runtime_status"] == "running"
    assert envelope.payload["debug"] is True


def test_envelope_is_immutable() -> None:
    envelope = Envelope(type="heartbeat")
    try:
        envelope.type = "system_status"  # type: ignore[misc]
    except (TypeError, ValueError):
        return
    msg = "expected Envelope to be frozen"
    raise AssertionError(msg)
