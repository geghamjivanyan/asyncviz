"""Ring-buffer tracer for the executor metrics engine."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

ExecutorMetricsTraceKind = Literal[
    "event-applied",
    "event-skipped",
    "updated-emitted",
    "saturation-changed",
    "contention-detected",
    "latency-spike-detected",
    "executor-evicted",
    "executor-finalized",
]


@dataclass(frozen=True, slots=True)
class ExecutorMetricsTraceEntry:
    kind: ExecutorMetricsTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[ExecutorMetricsTraceEntry] = deque(maxlen=_CAPACITY)


def is_executor_metrics_trace_enabled() -> bool:
    return _enabled


def set_executor_metrics_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_executor_metrics_trace(kind: ExecutorMetricsTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(
        ExecutorMetricsTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()),
    )


def get_executor_metrics_trace() -> tuple[ExecutorMetricsTraceEntry, ...]:
    return tuple(_ring)


def clear_executor_metrics_trace() -> None:
    _ring.clear()
