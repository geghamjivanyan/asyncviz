"""Ring-buffer tracer for the recording engine.

Disabled by default. Flip on via :func:`set_recording_trace_enabled`
to chase append-ordering or recovery bugs during development.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

RecordingTraceKind = Literal[
    "session-started",
    "session-stopped",
    "event-appended",
    "event-dropped",
    "flush-completed",
    "flush-failed",
    "chunk-rotated",
    "snapshot-captured",
    "manifest-written",
    "recovery-started",
    "recovery-completed",
    "integrity-failure",
    "recursion-skip",
]


@dataclass(frozen=True, slots=True)
class RecordingTraceEntry:
    kind: RecordingTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[RecordingTraceEntry] = deque(maxlen=_CAPACITY)


def is_recording_trace_enabled() -> bool:
    return _enabled


def set_recording_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_recording_trace(kind: RecordingTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(
        RecordingTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()),
    )


def get_recording_trace() -> tuple[RecordingTraceEntry, ...]:
    return tuple(_ring)


def clear_recording_trace() -> None:
    _ring.clear()
