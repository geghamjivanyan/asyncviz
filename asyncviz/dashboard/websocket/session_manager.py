"""Per-runtime websocket session registry.

Distinct from :class:`asyncviz.dashboard.websocket.manager.ConnectionManager`:
the connection manager is the wire-level broadcast surface (it broadcasts
to *every* connected socket); this :class:`SessionManager` is the
gateway-level registry of typed :class:`WebSocketSession` records.

Both are wired up by the dashboard lifespan. The gateway uses the session
manager to track lifecycle + per-session metrics; the bridge keeps using
the connection manager for fanout.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.dashboard.websocket.sessions import (
    SessionMetrics,
    SessionState,
    WebSocketSession,
)


@dataclass(frozen=True, slots=True)
class SessionRegistrySnapshot:
    """Aggregate view across all active sessions."""

    total_active: int
    by_state: dict[str, int]
    aggregate: SessionMetrics


class SessionRegistry:
    """Threadsafe ``session_id → WebSocketSession`` map.

    Operations are O(1) for insert / lookup / removal. Readers receive
    tuple snapshots so the lock doesn't span downstream code.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_id: dict[str, WebSocketSession] = {}
        self._closed_total = 0
        self._opened_total = 0

    @property
    def opened_total(self) -> int:
        with self._lock:
            return self._opened_total

    @property
    def closed_total(self) -> int:
        with self._lock:
            return self._closed_total

    def add(self, session: WebSocketSession) -> None:
        with self._lock:
            self._by_id[session.session_id] = session
            self._opened_total += 1

    def remove(self, session_id: str) -> WebSocketSession | None:
        with self._lock:
            session = self._by_id.pop(session_id, None)
            if session is not None:
                self._closed_total += 1
            return session

    def get(self, session_id: str) -> WebSocketSession | None:
        with self._lock:
            return self._by_id.get(session_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_id)

    def __contains__(self, session_id: object) -> bool:
        if not isinstance(session_id, str):
            return False
        with self._lock:
            return session_id in self._by_id

    def active_view(self) -> tuple[WebSocketSession, ...]:
        with self._lock:
            return tuple(self._by_id.values())

    def by_state(self) -> dict[str, int]:
        with self._lock:
            buckets: dict[str, int] = {}
            for session in self._by_id.values():
                buckets[session.state.value] = buckets.get(session.state.value, 0) + 1
            return buckets

    def aggregate_metrics(self) -> SessionMetrics:
        """Sum every per-session counter into one aggregate."""
        agg = SessionMetrics()
        with self._lock:
            sessions = list(self._by_id.values())
        for s in sessions:
            snap = s.snapshot_metrics()
            agg.messages_sent += snap.messages_sent
            agg.messages_dropped += snap.messages_dropped
            agg.heartbeats_sent += snap.heartbeats_sent
            agg.heartbeats_missed += snap.heartbeats_missed
            agg.send_failures += snap.send_failures
            agg.bytes_sent += snap.bytes_sent
            agg.backpressure_events += snap.backpressure_events
        return agg

    def snapshot(self) -> SessionRegistrySnapshot:
        return SessionRegistrySnapshot(
            total_active=len(self),
            by_state=self.by_state(),
            aggregate=self.aggregate_metrics(),
        )

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()


def _mark_all_closed(registry: SessionRegistry) -> None:
    """Best-effort: flip every session into ``CLOSED`` state."""
    for session in registry.active_view():
        session.mark_state(SessionState.CLOSED)
