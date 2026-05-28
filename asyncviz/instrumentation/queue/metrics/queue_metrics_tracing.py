"""Ring-buffer tracer for the queue metrics engine.

Disabled by default. Switch on via :func:`set_queue_metrics_trace_enabled`
to debug pressure flips / saturation detection during development. The
buffer is bounded so leaving it on in production wouldn't accumulate
memory — though it adds a small per-event cost, so keep it off there.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

QueueMetricsTraceKind = Literal[
    "event-applied",
    "event-skipped",
    "updated-emitted",
    "pressure-changed",
    "contention-detected",
    "saturation-detected",
    "queue-evicted",
    "queue-finalized",
]


@dataclass(frozen=True, slots=True)
class QueueMetricsTraceEntry:
    kind: QueueMetricsTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[QueueMetricsTraceEntry] = deque(maxlen=_CAPACITY)


def is_queue_metrics_trace_enabled() -> bool:
    return _enabled


def set_queue_metrics_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_queue_metrics_trace(kind: QueueMetricsTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(
        QueueMetricsTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()),
    )


def get_queue_metrics_trace() -> tuple[QueueMetricsTraceEntry, ...]:
    return tuple(_ring)


def clear_queue_metrics_trace() -> None:
    _ring.clear()
