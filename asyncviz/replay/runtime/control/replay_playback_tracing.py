"""256-entry trace ring for coordination lifecycle events."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Literal

CoordinationTraceKind = Literal[
    "pause-requested",
    "pause-began",
    "pause-completed",
    "pause-cancelled",
    "resume-requested",
    "resume-began",
    "resume-completed",
    "step-requested",
    "step-completed",
    "transition",
    "transition-illegal",
    "backpressure",
    "barrier-resolved",
    "barrier-timeout",
    "coalesced",
]

_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class CoordinationTraceEntry:
    monotonic_ns: int
    kind: CoordinationTraceKind
    detail: str


class _Ring:
    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: deque[CoordinationTraceEntry] = deque(maxlen=_CAPACITY)
        self._lock = threading.Lock()

    def push(self, entry: CoordinationTraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[CoordinationTraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_RING = _Ring()
_enabled: bool = False


def set_coordination_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _RING.clear()


def is_coordination_trace_enabled() -> bool:
    return _enabled


def record_coordination_trace(
    kind: CoordinationTraceKind, detail: str = "",
) -> None:
    if not _enabled:
        return
    _RING.push(
        CoordinationTraceEntry(
            monotonic_ns=time.monotonic_ns(), kind=kind, detail=detail,
        ),
    )


def get_coordination_trace() -> tuple[CoordinationTraceEntry, ...]:
    return _RING.snapshot()


def clear_coordination_trace() -> None:
    _RING.clear()
