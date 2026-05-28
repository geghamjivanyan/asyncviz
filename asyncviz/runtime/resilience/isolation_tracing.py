"""Resilience-layer trace ring buffer."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

IsolationTraceKind = Literal[
    "subsystem-registered",
    "failure-observed",
    "breaker-trip",
    "breaker-close",
    "boundary-admitted",
    "boundary-rejected",
    "payload-quarantined",
    "recovery-attempt",
    "recovery-outcome",
    "mode-transition",
    "diagnostic",
]


@dataclass(frozen=True, slots=True)
class IsolationTraceEntry:
    kind: IsolationTraceKind
    detail: str
    at_ns: int


_DEFAULT_CAPACITY = 256
_lock = threading.Lock()
_enabled = False
_capacity = _DEFAULT_CAPACITY
_ring: deque[IsolationTraceEntry] = deque(maxlen=_DEFAULT_CAPACITY)


def set_isolation_trace_enabled(value: bool, *, capacity: int | None = None) -> None:
    global _enabled, _capacity, _ring
    with _lock:
        _enabled = value
        if capacity is not None:
            _capacity = capacity
            _ring = deque(_ring, maxlen=capacity)
        if not value:
            _ring.clear()


def is_isolation_trace_enabled() -> bool:
    with _lock:
        return _enabled


def record_isolation_trace(kind: IsolationTraceKind, detail: str) -> None:
    with _lock:
        if not _enabled:
            return
        _ring.append(
            IsolationTraceEntry(kind=kind, detail=detail, at_ns=time.monotonic_ns()),
        )


def get_isolation_trace() -> tuple[IsolationTraceEntry, ...]:
    with _lock:
        return tuple(_ring)


def clear_isolation_trace() -> None:
    with _lock:
        _ring.clear()


def isolation_trace_capacity() -> int:
    with _lock:
        return _capacity
