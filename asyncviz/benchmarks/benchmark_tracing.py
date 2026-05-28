"""256-entry benchmark trace ring."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Literal

BenchmarkTraceKind = Literal[
    "suite-started",
    "suite-completed",
    "benchmark-started",
    "benchmark-completed",
    "benchmark-failed",
    "benchmark-slow",
    "regression-detected",
    "improvement-detected",
    "baseline-loaded",
    "baseline-written",
    "report-emitted",
]

_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class BenchmarkTraceEntry:
    monotonic_ns: int
    kind: BenchmarkTraceKind
    detail: str


class _Ring:
    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: deque[BenchmarkTraceEntry] = deque(maxlen=_CAPACITY)
        self._lock = threading.Lock()

    def push(self, entry: BenchmarkTraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[BenchmarkTraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_RING = _Ring()
_enabled: bool = False


def set_benchmark_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _RING.clear()


def is_benchmark_trace_enabled() -> bool:
    return _enabled


def record_benchmark_trace(kind: BenchmarkTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _RING.push(
        BenchmarkTraceEntry(
            monotonic_ns=time.monotonic_ns(), kind=kind, detail=detail,
        ),
    )


def get_benchmark_trace() -> tuple[BenchmarkTraceEntry, ...]:
    return _RING.snapshot()


def clear_benchmark_trace() -> None:
    _RING.clear()
