"""Typed websocket session model."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from asyncviz.dashboard.websocket.client import WebSocketClient


class SessionState(StrEnum):
    """Lifecycle states a session can be in."""

    PENDING = "pending"  # accepted, before handshake completes
    HYDRATING = "hydrating"  # snapshot / replay in flight
    LIVE = "live"  # streaming live events
    DRAINING = "draining"  # peer disconnected; flushing in-flight sends
    CLOSED = "closed"


@dataclass(slots=True)
class ReplayCursor:
    """Per-session replay bookkeeping.

    ``last_sequence_sent`` is the canonical resume point for the *next*
    reconnect from this session. ``replayed_frames`` counts the frames
    actually streamed during the handshake (zero for fresh connects).
    """

    last_sequence_sent: int = 0
    replayed_frames: int = 0
    requested_since: int = 0
    hit: bool = True
    used_checkpoint: bool = False


@dataclass(slots=True)
class SessionMetrics:
    """Per-session running counters."""

    messages_sent: int = 0
    messages_dropped: int = 0
    heartbeats_sent: int = 0
    heartbeats_missed: int = 0
    send_failures: int = 0
    bytes_sent: int = 0
    backpressure_events: int = 0


@dataclass(slots=True)
class WebSocketSession:
    """Mutable per-connection state.

    Created by the gateway when a client connects; destroyed when the
    connection closes. Reads + writes happen under the session's own lock
    so heartbeat / streaming / disconnect can race without corrupting
    counters.
    """

    session_id: str
    client: WebSocketClient
    state: SessionState
    connected_at_wall: float
    connected_at_monotonic_ns: int
    runtime_id: str
    remote: str | None = None
    replay: ReplayCursor = field(default_factory=ReplayCursor)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)
    last_activity_monotonic_ns: int = 0
    last_heartbeat_at_monotonic_ns: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def client_id(self) -> str:
        return self.client.id

    def mark_state(self, state: SessionState) -> None:
        with self._lock:
            self.state = state

    def record_sent(self, *, byte_count: int) -> None:
        with self._lock:
            self.metrics.messages_sent += 1
            self.metrics.bytes_sent += byte_count

    def record_dropped(self) -> None:
        with self._lock:
            self.metrics.messages_dropped += 1
            self.metrics.backpressure_events += 1

    def record_send_failure(self) -> None:
        with self._lock:
            self.metrics.send_failures += 1

    def record_heartbeat_sent(self, *, monotonic_ns: int) -> None:
        with self._lock:
            self.metrics.heartbeats_sent += 1
            self.last_heartbeat_at_monotonic_ns = monotonic_ns
            self.last_activity_monotonic_ns = monotonic_ns

    def record_heartbeat_missed(self) -> None:
        with self._lock:
            self.metrics.heartbeats_missed += 1

    def advance_sequence(self, sequence: int) -> None:
        with self._lock:
            if sequence > self.replay.last_sequence_sent:
                self.replay.last_sequence_sent = sequence

    def snapshot_metrics(self) -> SessionMetrics:
        with self._lock:
            return SessionMetrics(
                messages_sent=self.metrics.messages_sent,
                messages_dropped=self.metrics.messages_dropped,
                heartbeats_sent=self.metrics.heartbeats_sent,
                heartbeats_missed=self.metrics.heartbeats_missed,
                send_failures=self.metrics.send_failures,
                bytes_sent=self.metrics.bytes_sent,
                backpressure_events=self.metrics.backpressure_events,
            )


def fresh_session_id() -> str:
    """uuid4 hex — replay-stable per-connection identifier."""
    return uuid.uuid4().hex
