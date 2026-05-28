"""256-entry speed-coordination trace ring."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Literal

SpeedTraceKind = Literal[
    "speed-requested",
    "speed-applied",
    "speed-coalesced",
    "speed-rejected",
    "speed-clamped",
    "speed-coordination-drop",
    "speed-integrity-violation",
    "drift-sample",
    "anchor-refreshed",
    "preset-cycled",
    "default-restored",
]

_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class SpeedTraceEntry:
    monotonic_ns: int
    kind: SpeedTraceKind
    detail: str


class _Ring:
    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: deque[SpeedTraceEntry] = deque(maxlen=_CAPACITY)
        self._lock = threading.Lock()

    def push(self, entry: SpeedTraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[SpeedTraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_RING = _Ring()
_enabled: bool = False


def set_speed_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _RING.clear()


def is_speed_trace_enabled() -> bool:
    return _enabled


def record_speed_trace(kind: SpeedTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _RING.push(
        SpeedTraceEntry(monotonic_ns=time.monotonic_ns(), kind=kind, detail=detail),
    )


def get_speed_trace() -> tuple[SpeedTraceEntry, ...]:
    return _RING.snapshot()


def clear_speed_trace() -> None:
    _RING.clear()
