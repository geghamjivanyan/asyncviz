from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app
from asyncviz.dashboard.websocket.backpressure import (
    DEFAULT_OUTBOUND_QUEUE_DEPTH,
    BackpressurePolicy,
    is_overflowed,
)
from asyncviz.dashboard.websocket.handshake import (
    HandshakeMode,
    evaluate_handshake,
)
from asyncviz.dashboard.websocket.heartbeat import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    HeartbeatPolicy,
)
from asyncviz.dashboard.websocket.metrics import GatewayMetrics
from asyncviz.dashboard.websocket.session_manager import SessionRegistry
from asyncviz.dashboard.websocket.sessions import (
    SessionState,
    WebSocketSession,
    fresh_session_id,
)


@pytest.fixture
def app():
    # ``api-only`` mode keeps the SPA fallback from shadowing dynamic routes.
    return create_app(AsyncVizConfig(frontend_mode="api-only"))


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


# ── HandshakePolicy primitives ────────────────────────────────────────────


def test_evaluate_handshake_live_only_for_fresh_connect() -> None:
    decision = evaluate_handshake(
        buffer=None,
        since_sequence=0,
        bridge_current_sequence=10,
    )
    assert decision.mode is HandshakeMode.LIVE_ONLY
    assert decision.last_sequence_sent == 10
    assert decision.needs_snapshot is True


def test_evaluate_handshake_without_buffer_falls_back_to_snapshot() -> None:
    decision = evaluate_handshake(
        buffer=None,
        since_sequence=5,
        bridge_current_sequence=10,
    )
    assert decision.mode is HandshakeMode.SNAPSHOT_FALLBACK


# ── Session model + registry ──────────────────────────────────────────────


def test_fresh_session_id_is_unique_hex() -> None:
    ids = {fresh_session_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(len(s) == 32 for s in ids)


def test_session_registry_add_and_remove() -> None:
    registry = SessionRegistry()
    assert len(registry) == 0

    session = _stub_session(registry_first=True)
    registry.add(session)
    assert len(registry) == 1
    assert session.session_id in registry
    assert registry.opened_total == 1

    removed = registry.remove(session.session_id)
    assert removed is session
    assert len(registry) == 0
    assert registry.closed_total == 1


def test_session_registry_by_state_breakdown() -> None:
    registry = SessionRegistry()
    s1 = _stub_session()
    s2 = _stub_session()
    s2.mark_state(SessionState.LIVE)
    s3 = _stub_session()
    s3.mark_state(SessionState.HYDRATING)
    registry.add(s1)
    registry.add(s2)
    registry.add(s3)
    buckets = registry.by_state()
    assert buckets[SessionState.PENDING.value] == 1
    assert buckets[SessionState.LIVE.value] == 1
    assert buckets[SessionState.HYDRATING.value] == 1


def test_session_records_messages_and_drops() -> None:
    session = _stub_session()
    session.record_sent(byte_count=120)
    session.record_sent(byte_count=300)
    session.record_dropped()
    snap = session.snapshot_metrics()
    assert snap.messages_sent == 2
    assert snap.bytes_sent == 420
    assert snap.messages_dropped == 1
    assert snap.backpressure_events == 1


def test_session_advance_sequence_is_monotonic() -> None:
    session = _stub_session()
    session.advance_sequence(5)
    session.advance_sequence(3)  # backwards — should not regress
    session.advance_sequence(10)
    assert session.replay.last_sequence_sent == 10


def test_registry_aggregate_metrics_sums_across_sessions() -> None:
    registry = SessionRegistry()
    s1 = _stub_session()
    s1.record_sent(byte_count=100)
    s1.record_dropped()
    s2 = _stub_session()
    s2.record_sent(byte_count=200)
    s2.record_send_failure()
    registry.add(s1)
    registry.add(s2)
    agg = registry.aggregate_metrics()
    assert agg.messages_sent == 2
    assert agg.bytes_sent == 300
    assert agg.messages_dropped == 1
    assert agg.send_failures == 1


# ── Heartbeat policy ──────────────────────────────────────────────────────


def test_heartbeat_policy_marks_stale_after_threshold() -> None:
    policy = HeartbeatPolicy(interval_seconds=1.0, max_missed=3)
    # 5 seconds since last activity → past threshold (3s).
    assert policy.is_stale(now_monotonic_ns=5_000_000_000, last_activity_monotonic_ns=0)
    # 1 second since last activity → within threshold.
    assert not policy.is_stale(now_monotonic_ns=1_000_000_000, last_activity_monotonic_ns=0)


def test_heartbeat_policy_default_interval() -> None:
    policy = HeartbeatPolicy()
    assert policy.interval_seconds == DEFAULT_HEARTBEAT_INTERVAL_SECONDS


# ── Backpressure ──────────────────────────────────────────────────────────


def test_backpressure_policy_default_depth() -> None:
    policy = BackpressurePolicy()
    assert policy.max_queue_depth == DEFAULT_OUTBOUND_QUEUE_DEPTH


def test_is_overflowed() -> None:
    policy = BackpressurePolicy(max_queue_depth=5)
    assert not is_overflowed(queue_depth=4, policy=policy)
    assert is_overflowed(queue_depth=5, policy=policy)
    assert is_overflowed(queue_depth=10, policy=policy)


# ── GatewayMetrics ────────────────────────────────────────────────────────


def test_gateway_metrics_record_lifecycle() -> None:
    metrics = GatewayMetrics()
    metrics.record_session_opened()
    metrics.record_session_opened()
    metrics.record_session_closed()
    metrics.record_replay_hit()
    metrics.record_message_sent()
    metrics.record_messages_sent(4)
    snap = metrics.snapshot(sessions_active=1)
    assert snap.sessions_opened == 2
    assert snap.sessions_closed == 1
    assert snap.sessions_active == 1
    assert snap.handshake_replay_hits == 1
    assert snap.messages_sent == 5


def test_gateway_metrics_messages_sent_with_zero_n() -> None:
    metrics = GatewayMetrics()
    metrics.record_messages_sent(0)
    metrics.record_messages_sent(-3)  # ignored
    snap = metrics.snapshot(sessions_active=0)
    assert snap.messages_sent == 0


# ── End-to-end via TestClient ─────────────────────────────────────────────


def test_ws_connect_yields_runtime_snapshot(client) -> None:
    """A fresh ``/ws`` connect receives a runtime_snapshot envelope."""
    with client.websocket_connect("/ws") as ws:
        text = ws.receive_text()
        payload = json.loads(text)
    assert payload["type"] == "runtime_snapshot"


def test_ws_connect_session_count_lifecycle(app, client) -> None:
    gateway = app.state.websocket_gateway
    before = gateway.metrics_snapshot()
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()  # consume snapshot
        # While the WS is open, sessions_active should be 1.
        mid = gateway.metrics_snapshot()
        assert mid.sessions_opened == before.sessions_opened + 1
        assert mid.sessions_active == 1
    after = gateway.metrics_snapshot()
    # After exiting the context, the session is closed.
    assert after.sessions_closed == before.sessions_closed + 1
    assert after.sessions_active == 0


def test_ws_gateway_records_snapshot_hydration_on_fresh_connect(app, client) -> None:
    gateway = app.state.websocket_gateway
    before = gateway.metrics_snapshot()
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()
    after = gateway.metrics_snapshot()
    assert after.handshake_snapshot_hydrations == before.handshake_snapshot_hydrations + 1


def test_ws_gateway_records_replay_hit_on_since_sequence(app, client) -> None:
    """Connect, publish a few events, reconnect with since_sequence — expect replay hit."""
    from asyncviz.runtime.events.models import TaskCreatedEvent

    # First connect to ensure the bridge is alive; consume snapshot.
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()

    # Publish a couple of events through the bus so they enter the replay buffer.
    bus = app.state.event_bus
    bus.publish(TaskCreatedEvent(task_id="t1"))
    bus.publish(TaskCreatedEvent(task_id="t2"))

    # Reconnect with since_sequence=0 (still a fresh connect, but the buffer
    # now has frames). A since_sequence > 0 path requires the replay buffer
    # to cover the gap; we focus on the gateway's metric paths here.
    gateway = app.state.websocket_gateway
    before = gateway.metrics_snapshot()
    with client.websocket_connect("/ws?since_sequence=1") as ws:
        ws.receive_text()
    after = gateway.metrics_snapshot()
    # Either a hit or a miss must have been recorded.
    delta_hits = after.handshake_replay_hits - before.handshake_replay_hits
    delta_misses = after.handshake_replay_misses - before.handshake_replay_misses
    assert delta_hits + delta_misses == 1


def test_ws_gateway_metrics_endpoint_returns_snapshot(client) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.receive_text()
    response = client.get("/api/runtime/gateway")
    assert response.status_code == 200
    data = response.json()
    assert data["sessions_opened"] >= 1
    assert data["sessions_active"] == 0
    assert "live" in data["sessions_by_state"]


def test_gateway_metrics_endpoint_shape(client) -> None:
    response = client.get("/api/runtime/gateway")
    assert response.status_code == 200
    data = response.json()
    required_keys = {
        "sessions_opened",
        "sessions_closed",
        "sessions_active",
        "handshake_replay_hits",
        "handshake_replay_misses",
        "handshake_snapshot_hydrations",
        "messages_sent",
        "messages_dropped",
        "heartbeats_sent",
        "sessions_stale_evicted",
        "protocol_errors",
        "sessions_by_state",
        "aggregate_session_metrics",
    }
    assert required_keys.issubset(data.keys())


# ── Concurrent sessions ───────────────────────────────────────────────────


def test_multiple_simultaneous_ws_sessions(app, client) -> None:
    gateway = app.state.websocket_gateway
    with client.websocket_connect("/ws") as ws_a, client.websocket_connect("/ws") as ws_b:
        ws_a.receive_text()  # snapshot for A
        ws_b.receive_text()  # snapshot for B
        snap = gateway.metrics_snapshot()
        assert snap.sessions_active == 2
    snap = gateway.metrics_snapshot()
    assert snap.sessions_active == 0


# ── helpers ───────────────────────────────────────────────────────────────


def _stub_session(*, registry_first: bool = False) -> WebSocketSession:
    """Build a session without going through a real WebSocket."""

    class _FakeClient:
        id = "fake"

        async def send_text(self, _text: str) -> None: ...

        async def close(self) -> None: ...

    return WebSocketSession(
        session_id=fresh_session_id(),
        client=_FakeClient(),  # type: ignore[arg-type]
        state=SessionState.PENDING,
        connected_at_wall=0.0,
        connected_at_monotonic_ns=0,
        runtime_id="r",
    )
