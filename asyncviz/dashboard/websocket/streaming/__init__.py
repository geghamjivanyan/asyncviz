"""Canonical realtime streaming layer for the dashboard websocket.

Public surface:

* :class:`RuntimeStreamingEngine` — subscribes to the runtime's metrics
  aggregator, warning manager, and timeline engine; broadcasts typed
  ``metrics_delta``, ``warning_delta``, and ``timeline_delta`` envelopes
  over the :class:`ConnectionManager` fanout.
* :class:`StreamingMetrics` / :class:`StreamingMetricsSnapshot` —
  observability counters surfaced via ``/api/runtime/streaming``.
* :class:`BatchingPolicy` — placeholder for the future micro-batching
  layer; the engine sends one envelope per delta today.
* :func:`metrics_delta_payload` / :func:`warning_delta_payload` —
  JSON-safe converters for incoming typed deltas. Centralizing the
  conversions keeps the wire shape in sync with the frontend's
  ``MetricsDeltaPayload`` / ``WarningDeltaPayload`` interfaces.
* exceptions — :class:`StreamingError`, :class:`StreamNotRunningError`,
  :class:`DuplicateSourceError`.
"""

from asyncviz.dashboard.websocket.streaming.batching import BatchingPolicy
from asyncviz.dashboard.websocket.streaming.engine import RuntimeStreamingEngine
from asyncviz.dashboard.websocket.streaming.envelopes import (
    metrics_delta_payload,
    runtime_event_payload_from,
    warning_delta_payload,
)
from asyncviz.dashboard.websocket.streaming.exceptions import (
    DuplicateSourceError,
    StreamingError,
    StreamNotRunningError,
)
from asyncviz.dashboard.websocket.streaming.metrics import (
    StreamingMetrics,
    StreamingMetricsSnapshot,
)

__all__ = [
    "BatchingPolicy",
    "DuplicateSourceError",
    "RuntimeStreamingEngine",
    "StreamNotRunningError",
    "StreamingError",
    "StreamingMetrics",
    "StreamingMetricsSnapshot",
    "metrics_delta_payload",
    "runtime_event_payload_from",
    "warning_delta_payload",
]
