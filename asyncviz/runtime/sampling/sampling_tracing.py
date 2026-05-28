"""256-entry sampling-layer trace ring."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Literal

SamplingTraceKind = Literal[
    "sampler-started",
    "sampler-reset",
    "event-retained",
    "event-dropped",
    "adaptive-overload-engaged",
    "adaptive-overload-released",
    "marker-emitted",
    "websocket-shed-engaged",
    "websocket-shed-released",
    "integrity-violation",
    "policy-replaced",
]

_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class SamplingTraceEntry:
    monotonic_ns: int
    kind: SamplingTraceKind
    detail: str


class _Ring:
    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: deque[SamplingTraceEntry] = deque(maxlen=_CAPACITY)
        self._lock = threading.Lock()

    def push(self, entry: SamplingTraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[SamplingTraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_RING = _Ring()
_enabled: bool = False


def set_sampling_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _RING.clear()


def is_sampling_trace_enabled() -> bool:
    return _enabled


def record_sampling_trace(kind: SamplingTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _RING.push(
        SamplingTraceEntry(
            monotonic_ns=time.monotonic_ns(), kind=kind, detail=detail,
        ),
    )


def get_sampling_trace() -> tuple[SamplingTraceEntry, ...]:
    return _RING.snapshot()


def clear_sampling_trace() -> None:
    _RING.clear()
