"""256-entry seek trace ring."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Literal

SeekTraceKind = Literal[
    "seek-requested",
    "seek-coalesced",
    "seek-started",
    "seek-completed",
    "seek-cancelled",
    "seek-failed",
    "cache-hit",
    "cache-miss",
    "checkpoint-hit",
    "snapshot-hit",
    "full-reconstruction",
    "integrity-violation",
    "budget-exceeded",
]

_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class SeekTraceEntry:
    monotonic_ns: int
    kind: SeekTraceKind
    detail: str


class _Ring:
    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: deque[SeekTraceEntry] = deque(maxlen=_CAPACITY)
        self._lock = threading.Lock()

    def push(self, entry: SeekTraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[SeekTraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_RING = _Ring()
_enabled: bool = False


def set_seek_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _RING.clear()


def is_seek_trace_enabled() -> bool:
    return _enabled


def record_seek_trace(kind: SeekTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _RING.push(
        SeekTraceEntry(monotonic_ns=time.monotonic_ns(), kind=kind, detail=detail),
    )


def get_seek_trace() -> tuple[SeekTraceEntry, ...]:
    return _RING.snapshot()


def clear_seek_trace() -> None:
    _RING.clear()
