"""Ring-buffer tracer for the replay recorder.

Disabled by default — the recorder calls into this on the hot path,
so the check has to be cheap. When enabled (via diagnostics or
tests), every interesting transition (chunk roll, flush, error,
shutdown) lands in the ring.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

RecorderTraceKind = Literal[
    "session-started",
    "session-finalized",
    "session-aborted",
    "chunk-rolled",
    "chunk-finalized",
    "flush",
    "writer-error",
    "event-dropped",
    "event-filtered",
    "snapshot-written",
]


@dataclass(frozen=True, slots=True)
class RecorderTraceEntry:
    kind: RecorderTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[RecorderTraceEntry] = deque(maxlen=_CAPACITY)


def is_recorder_trace_enabled() -> bool:
    return _enabled


def set_recorder_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_recorder_trace(kind: RecorderTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(RecorderTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()))


def get_recorder_trace() -> tuple[RecorderTraceEntry, ...]:
    return tuple(_ring)


def clear_recorder_trace() -> None:
    _ring.clear()
