"""Bounded trace ring for replay-loader lifecycle events."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Literal

ReplayTraceKind = Literal[
    "session-opened",
    "session-closed",
    "chunk-opened",
    "chunk-closed",
    "chunk-skipped",
    "frame-yielded",
    "frame-dropped",
    "seek-started",
    "seek-completed",
    "snapshot-loaded",
    "integrity-failed",
    "state-reconstructed",
    "filter-drop",
    "window-drop",
    "recovery-applied",
]

_TRACE_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class ReplayTraceEntry:
    monotonic_ns: int
    kind: ReplayTraceKind
    detail: str


class _TraceRing:
    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: deque[ReplayTraceEntry] = deque(maxlen=_TRACE_CAPACITY)
        self._lock = threading.Lock()

    def push(self, entry: ReplayTraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[ReplayTraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_RING: _TraceRing = _TraceRing()
_enabled: bool = False


def set_replay_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _RING.clear()


def is_replay_trace_enabled() -> bool:
    return _enabled


def record_replay_trace(kind: ReplayTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _RING.push(ReplayTraceEntry(monotonic_ns=time.monotonic_ns(), kind=kind, detail=detail))


def get_replay_trace() -> tuple[ReplayTraceEntry, ...]:
    return _RING.snapshot()


def clear_replay_trace() -> None:
    _RING.clear()
