"""Ring-buffer tracer for queue instrumentation."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

QueueTraceKind = Literal[
    "queue-registered",
    "queue-finalized",
    "queue-put",
    "queue-get",
    "queue-full-wait",
    "queue-empty-wait",
    "queue-task-done",
    "queue-cancelled",
    "recursion-skip",
    "event-dropped",
]


@dataclass(frozen=True, slots=True)
class QueueTraceEntry:
    kind: QueueTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[QueueTraceEntry] = deque(maxlen=_CAPACITY)


def is_queue_trace_enabled() -> bool:
    return _enabled


def set_queue_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_queue_trace(kind: QueueTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(QueueTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()))


def get_queue_trace() -> tuple[QueueTraceEntry, ...]:
    return tuple(_ring)


def clear_queue_trace() -> None:
    _ring.clear()
