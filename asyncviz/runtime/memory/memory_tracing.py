"""256-entry memory-optimizer trace ring."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Literal

MemoryTraceKind = Literal[
    "interner-bypassed",
    "compact-event-built",
    "compact-frame-built",
    "pool-acquired",
    "pool-released",
    "pool-double-release",
    "dedup-hit",
    "dedup-miss",
    "reducer-evicted",
    "topology-evicted",
    "websocket-buffer-grown",
    "replay-cache-evicted",
    "memory-threshold-breached",
]

_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class MemoryTraceEntry:
    monotonic_ns: int
    kind: MemoryTraceKind
    detail: str


class _Ring:
    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: deque[MemoryTraceEntry] = deque(maxlen=_CAPACITY)
        self._lock = threading.Lock()

    def push(self, entry: MemoryTraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[MemoryTraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_RING = _Ring()
_enabled: bool = False


def set_memory_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _RING.clear()


def is_memory_trace_enabled() -> bool:
    return _enabled


def record_memory_trace(kind: MemoryTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _RING.push(
        MemoryTraceEntry(
            monotonic_ns=time.monotonic_ns(), kind=kind, detail=detail,
        ),
    )


def get_memory_trace() -> tuple[MemoryTraceEntry, ...]:
    return _RING.snapshot()


def clear_memory_trace() -> None:
    _RING.clear()
