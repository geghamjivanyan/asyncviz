"""Canonical websocket gateway.

Orchestrates the per-connection lifecycle:

1. Accept the socket via :class:`ConnectionManager`.
2. Allocate a :class:`WebSocketSession`.
3. Run the :func:`evaluate_handshake` decision and stream the chosen
   handshake frames (snapshot, replay batch, or live-only).
4. Transition the session into :class:`SessionState.LIVE`.
5. On disconnect, mark the session :class:`SessionState.CLOSED` and
   tear it down.

The gateway does NOT do its own broadcast pumping — the existing
:class:`WebSocketBridge` is still the canonical event source for live
frames. The gateway's job is per-session orchestration + observability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import WebSocket

from asyncviz.dashboard.websocket.backpressure import BackpressurePolicy
from asyncviz.dashboard.websocket.exceptions import GatewayError
from asyncviz.dashboard.websocket.handshake import (
    HandshakeDecision,
    HandshakeMode,
    evaluate_handshake,
)
from asyncviz.dashboard.websocket.heartbeat import HeartbeatPolicy
from asyncviz.dashboard.websocket.metrics import (
    GatewayMetrics,
    GatewayMetricsSnapshot,
)
from asyncviz.dashboard.websocket.protocol import (
    Envelope,
    runtime_event,
)
from asyncviz.dashboard.websocket.session_manager import (
    SessionRegistry,
    SessionRegistrySnapshot,
)
from asyncviz.dashboard.websocket.sessions import (
    SessionState,
    WebSocketSession,
    fresh_session_id,
)
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.dashboard.state.backend_metrics import BackendMetrics
    from asyncviz.dashboard.websocket.bridge import WebSocketBridge
    from asyncviz.dashboard.websocket.client import WebSocketClient
    from asyncviz.dashboard.websocket.manager import ConnectionManager
    from asyncviz.runtime.clock import RuntimeClock
    from asyncviz.runtime.replay import EventReplayBuffer
    from asyncviz.runtime.tasks import TaskRegistry

logger = get_logger("dashboard.websocket.gateway")


@dataclass(frozen=True, slots=True)
class HandshakeResult:
    """What :meth:`WebSocketGateway.handshake` produced."""

    session: WebSocketSession
    decision: HandshakeDecision
    frames_streamed: int


class WebSocketGateway:
    """Authoritative per-session orchestrator.

    Composes:

    * :class:`ConnectionManager` — the wire-level accept/broadcast surface.
    * :class:`SessionRegistry` — typed per-connection state.
    * :class:`WebSocketBridge` — the canonical event pump (for snapshots
      + live broadcasts; the gateway doesn't replace it).
    * :class:`EventReplayBuffer` — replay log used during handshake.
    """

    def __init__(
        self,
        *,
        manager: ConnectionManager,
        bridge: WebSocketBridge,
        clock: RuntimeClock,
        registry: TaskRegistry,
        replay_buffer: EventReplayBuffer | None = None,
        backend_metrics: BackendMetrics | None = None,
        heartbeat: HeartbeatPolicy | None = None,
        backpressure: BackpressurePolicy | None = None,
    ) -> None:
        self._manager = manager
        self._bridge = bridge
        self._clock = clock
        self._registry = registry
        self._replay_buffer = replay_buffer
        self._backend_metrics = backend_metrics
        self._heartbeat = heartbeat or HeartbeatPolicy()
        self._backpressure = backpressure or BackpressurePolicy()
        self._metrics = GatewayMetrics()
        self._sessions = SessionRegistry()

    # ── identity ─────────────────────────────────────────────────────────
    @property
    def metrics(self) -> GatewayMetrics:
        return self._metrics

    @property
    def sessions(self) -> SessionRegistry:
        return self._sessions

    @property
    def heartbeat_policy(self) -> HeartbeatPolicy:
        return self._heartbeat

    @property
    def backpressure_policy(self) -> BackpressurePolicy:
        return self._backpressure

    # ── connection lifecycle ─────────────────────────────────────────────
    async def connect(self, websocket: WebSocket) -> WebSocketSession:
        """Accept ``websocket`` and create a :class:`WebSocketSession`."""
        client = await self._manager.connect(websocket)
        session = WebSocketSession(
            session_id=fresh_session_id(),
            client=client,
            state=SessionState.PENDING,
            connected_at_wall=self._clock.now(),
            connected_at_monotonic_ns=self._clock.monotonic_ns(),
            runtime_id=str(self._clock.runtime_id),
            remote=_remote_addr(websocket),
        )
        session.last_activity_monotonic_ns = session.connected_at_monotonic_ns
        self._sessions.add(session)
        self._metrics.record_session_opened()
        if self._backend_metrics is not None:
            self._backend_metrics.record_ws_connect()
        logger.debug(
            "session %s connected (client=%s remote=%s)",
            session.session_id,
            client.id,
            session.remote,
        )
        return session

    async def disconnect(self, session: WebSocketSession) -> None:
        """Mark the session closed and tear down the connection."""
        session.mark_state(SessionState.CLOSED)
        await self._manager.disconnect(session.client_id)
        self._sessions.remove(session.session_id)
        self._metrics.record_session_closed()
        if self._backend_metrics is not None:
            self._backend_metrics.record_ws_disconnect()
        logger.debug("session %s closed", session.session_id)

    async def evict_stale_sessions(self) -> int:
        """Iterate sessions, evicting any that have crossed the heartbeat-miss threshold."""
        now_ns = self._clock.monotonic_ns()
        evicted = 0
        for session in self._sessions.active_view():
            if session.state in (SessionState.CLOSED, SessionState.DRAINING):
                continue
            if self._heartbeat.is_stale(
                now_monotonic_ns=now_ns,
                last_activity_monotonic_ns=session.last_activity_monotonic_ns,
            ):
                logger.info(
                    "session %s evicted (stale; last_activity=%dns ago)",
                    session.session_id,
                    now_ns - session.last_activity_monotonic_ns,
                )
                session.record_heartbeat_missed()
                await self.disconnect(session)
                self._metrics.record_stale_eviction()
                evicted += 1
        return evicted

    # ── handshake ────────────────────────────────────────────────────────
    async def handshake(
        self,
        session: WebSocketSession,
        *,
        since_sequence: int,
    ) -> HandshakeResult:
        """Run the replay-aware handshake."""
        session.mark_state(SessionState.HYDRATING)
        session.replay.requested_since = since_sequence

        decision = evaluate_handshake(
            buffer=self._replay_buffer,
            since_sequence=since_sequence,
            bridge_current_sequence=self._bridge.current_sequence,
        )

        frames_streamed = 0
        if decision.mode is HandshakeMode.REPLAY:
            assert decision.replay is not None
            frames_streamed = await self._stream_replay(session, decision)
            session.replay.hit = True
            self._metrics.record_replay_hit()
        elif decision.mode is HandshakeMode.SNAPSHOT_FALLBACK:
            await self._send_snapshot(session)
            session.replay.hit = False
            self._metrics.record_replay_miss()
            self._metrics.record_snapshot_hydration()
            if decision.replay is not None and decision.replay.checkpoint is not None:
                session.replay.used_checkpoint = True
        else:  # LIVE_ONLY → fresh connect, snapshot baseline
            await self._send_snapshot(session)
            self._metrics.record_snapshot_hydration()

        # Advance the cursor to the high-water mark so subsequent live frames
        # don't fall behind it.
        session.advance_sequence(decision.last_sequence_sent)
        session.mark_state(SessionState.LIVE)
        return HandshakeResult(
            session=session,
            decision=decision,
            frames_streamed=frames_streamed,
        )

    async def _stream_replay(
        self,
        session: WebSocketSession,
        decision: HandshakeDecision,
    ) -> int:
        assert decision.replay is not None
        sent = 0
        for frame in decision.replay.window.frames:
            envelope = runtime_event(frame.payload, sequence=frame.sequence)
            ok = await self._send_envelope(session, envelope)
            if ok:
                sent += 1
                session.advance_sequence(frame.sequence)
                session.replay.replayed_frames += 1
            else:
                break
        return sent

    async def _send_snapshot(self, session: WebSocketSession) -> None:
        envelope = self._bridge.capture_snapshot(self._registry)
        await self._send_envelope(session, envelope)

    # ── live streaming ──────────────────────────────────────────────────
    async def keep_alive(self, session: WebSocketSession, websocket: WebSocket) -> None:
        """Block until the peer disconnects.

        Inbound messages are reserved for the future bidirectional protocol;
        for now we just count any received frame as activity so the
        heartbeat policy stays honest.

        Tolerates the full set of graceful-close artefacts ``receive_text``
        can raise during teardown — ``WebSocketDisconnect`` from
        Starlette, ``ConnectionClosed{Error,OK}`` from the underlying
        ``websockets`` library, and ``asyncio.CancelledError`` when the
        route handler is cancelled by the shutdown coordinator. All of
        those mean "peer is gone, exit the loop cleanly"; anything
        else surfaces.
        """
        from asyncviz.dashboard.websocket.shutdown_filter import (
            is_expected_websocket_close,
        )

        try:
            while True:
                _ = await websocket.receive_text()
                session.last_activity_monotonic_ns = self._clock.monotonic_ns()
        except GatewayError:
            self._metrics.record_protocol_error()
            raise
        except BaseException as exc:
            if is_expected_websocket_close(exc):
                return
            raise

    # ── send helpers ────────────────────────────────────────────────────
    async def _send_envelope(
        self,
        session: WebSocketSession,
        envelope: Envelope,
    ) -> bool:
        """Send one envelope; counts on success, drops + counts on failure."""
        try:
            payload = envelope.model_dump_json()
        except Exception as exc:
            logger.warning(
                "session %s: failed to serialize %r envelope: %s",
                session.session_id,
                envelope.type,
                exc,
            )
            session.record_send_failure()
            return False
        try:
            await session.client.send_text(payload)
        except Exception as exc:
            logger.debug(
                "session %s: send failed (%s); marking failure",
                session.session_id,
                exc,
            )
            session.record_send_failure()
            return False
        session.record_sent(byte_count=len(payload))
        session.last_activity_monotonic_ns = self._clock.monotonic_ns()
        self._metrics.record_message_sent()
        return True

    # ── observability ───────────────────────────────────────────────────
    def metrics_snapshot(self) -> GatewayMetricsSnapshot:
        return self._metrics.snapshot(sessions_active=len(self._sessions))

    def sessions_snapshot(self) -> SessionRegistrySnapshot:
        return self._sessions.snapshot()


def _remote_addr(websocket: WebSocket) -> str | None:
    client = getattr(websocket, "client", None)
    if client is None:
        return None
    host = getattr(client, "host", None)
    port = getattr(client, "port", None)
    if host is None:
        return None
    if port is not None:
        return f"{host}:{port}"
    return str(host)


def _get_client(session: WebSocketSession) -> WebSocketClient:
    """Public-facing convenience getter (kept thin for typing)."""
    return session.client
