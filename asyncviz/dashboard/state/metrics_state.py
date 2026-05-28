from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class MetricsSnapshot:
    events_emitted: int
    websocket_messages_sent: int


@dataclass
class MetricsState:
    """Thread-safe counters for dashboard-side metrics.

    Values are placeholders until instrumentation feeds real numbers in.
    """

    _events_emitted: int = 0
    _ws_messages_sent: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def inc_events(self, n: int = 1) -> None:
        with self._lock:
            self._events_emitted += n

    def inc_ws_messages(self, n: int = 1) -> None:
        with self._lock:
            self._ws_messages_sent += n

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            return MetricsSnapshot(
                events_emitted=self._events_emitted,
                websocket_messages_sent=self._ws_messages_sent,
            )
