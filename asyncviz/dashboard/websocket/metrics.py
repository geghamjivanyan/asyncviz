"""Gateway-level observability counters."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GatewayMetricsSnapshot:
    """Immutable view of :class:`GatewayMetrics`."""

    sessions_opened: int
    sessions_closed: int
    sessions_active: int
    handshake_replay_hits: int
    handshake_replay_misses: int
    handshake_snapshot_hydrations: int
    messages_sent: int
    messages_dropped: int
    heartbeats_sent: int
    sessions_stale_evicted: int
    protocol_errors: int


class GatewayMetrics:
    """Counters owned by :class:`WebSocketGateway`."""

    __slots__ = (
        "_handshake_replay_hits",
        "_handshake_replay_misses",
        "_handshake_snapshot_hydrations",
        "_heartbeats_sent",
        "_lock",
        "_messages_dropped",
        "_messages_sent",
        "_protocol_errors",
        "_sessions_closed",
        "_sessions_opened",
        "_sessions_stale_evicted",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions_opened = 0
        self._sessions_closed = 0
        self._handshake_replay_hits = 0
        self._handshake_replay_misses = 0
        self._handshake_snapshot_hydrations = 0
        self._messages_sent = 0
        self._messages_dropped = 0
        self._heartbeats_sent = 0
        self._sessions_stale_evicted = 0
        self._protocol_errors = 0

    def record_session_opened(self) -> None:
        with self._lock:
            self._sessions_opened += 1

    def record_session_closed(self) -> None:
        with self._lock:
            self._sessions_closed += 1

    def record_replay_hit(self) -> None:
        with self._lock:
            self._handshake_replay_hits += 1

    def record_replay_miss(self) -> None:
        with self._lock:
            self._handshake_replay_misses += 1

    def record_snapshot_hydration(self) -> None:
        with self._lock:
            self._handshake_snapshot_hydrations += 1

    def record_message_sent(self) -> None:
        with self._lock:
            self._messages_sent += 1

    def record_messages_sent(self, n: int) -> None:
        if n <= 0:
            return
        with self._lock:
            self._messages_sent += n

    def record_message_dropped(self) -> None:
        with self._lock:
            self._messages_dropped += 1

    def record_heartbeat(self) -> None:
        with self._lock:
            self._heartbeats_sent += 1

    def record_stale_eviction(self) -> None:
        with self._lock:
            self._sessions_stale_evicted += 1

    def record_protocol_error(self) -> None:
        with self._lock:
            self._protocol_errors += 1

    def snapshot(self, *, sessions_active: int) -> GatewayMetricsSnapshot:
        with self._lock:
            return GatewayMetricsSnapshot(
                sessions_opened=self._sessions_opened,
                sessions_closed=self._sessions_closed,
                sessions_active=sessions_active,
                handshake_replay_hits=self._handshake_replay_hits,
                handshake_replay_misses=self._handshake_replay_misses,
                handshake_snapshot_hydrations=self._handshake_snapshot_hydrations,
                messages_sent=self._messages_sent,
                messages_dropped=self._messages_dropped,
                heartbeats_sent=self._heartbeats_sent,
                sessions_stale_evicted=self._sessions_stale_evicted,
                protocol_errors=self._protocol_errors,
            )
