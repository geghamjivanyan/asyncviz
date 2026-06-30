"""256-entry backpressure-layer trace ring."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Literal

BackpressureTraceKind = Literal[
    "controller-started",
    "controller-reset",
    "state-upgraded",
    "state-downgraded",
    "emergency-entered",
    "emergency-released",
    "action-dispatched",
    "event-rejected",
    "event-evicted",
    "subscriber-slow",
    "subscriber-disconnected",
    "overflow-marker-emitted",
    "integrity-violation",
]

_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class BackpressureTraceEntry:
    monotonic_ns: int
    kind: BackpressureTraceKind
    detail: str


class _Ring:
    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: deque[BackpressureTraceEntry] = deque(maxlen=_CAPACITY)
        self._lock = threading.Lock()

    def push(self, entry: BackpressureTraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[BackpressureTraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_RING = _Ring()
_enabled: bool = False


def set_backpressure_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _RING.clear()


def is_backpressure_trace_enabled() -> bool:
    return _enabled


def record_backpressure_trace(
    kind: BackpressureTraceKind,
    detail: str = "",
) -> None:
    if not _enabled:
        return
    _RING.push(
        BackpressureTraceEntry(
            monotonic_ns=time.monotonic_ns(),
            kind=kind,
            detail=detail,
        ),
    )


def get_backpressure_trace() -> tuple[BackpressureTraceEntry, ...]:
    return _RING.snapshot()


def clear_backpressure_trace() -> None:
    _RING.clear()
