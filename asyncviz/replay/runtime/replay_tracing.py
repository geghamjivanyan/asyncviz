"""Engine-side trace ring."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Literal

ReplayEngineTraceKind = Literal[
    "engine-started",
    "engine-stopped",
    "frame-dispatched",
    "frame-skipped",
    "reducer-applied",
    "checkpoint-recorded",
    "snapshot-restored",
    "seek-started",
    "seek-completed",
    "pause",
    "resume",
    "speed-changed",
    "integrity-violation",
    "backpressure",
    "sink-failure",
]

_TRACE_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class ReplayEngineTraceEntry:
    monotonic_ns: int
    kind: ReplayEngineTraceKind
    detail: str


class _TraceRing:
    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: deque[ReplayEngineTraceEntry] = deque(maxlen=_TRACE_CAPACITY)
        self._lock = threading.Lock()

    def push(self, entry: ReplayEngineTraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[ReplayEngineTraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_RING: _TraceRing = _TraceRing()
_enabled: bool = False


def set_engine_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _RING.clear()


def is_engine_trace_enabled() -> bool:
    return _enabled


def record_engine_trace(kind: ReplayEngineTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _RING.push(
        ReplayEngineTraceEntry(monotonic_ns=time.monotonic_ns(), kind=kind, detail=detail),
    )


def get_engine_trace() -> tuple[ReplayEngineTraceEntry, ...]:
    return _RING.snapshot()


def clear_engine_trace() -> None:
    _RING.clear()
