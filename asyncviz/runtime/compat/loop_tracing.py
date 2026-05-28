"""Loop-compat trace ring buffer."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

LoopCompatTraceKind = Literal[
    "manager-attached",
    "manager-detached",
    "uvloop-install-attempt",
    "uvloop-install-success",
    "uvloop-install-failure",
    "fallback",
    "drift-warning",
    "integrity-violation",
    "diagnostic",
]


@dataclass(frozen=True, slots=True)
class LoopCompatTraceEntry:
    kind: LoopCompatTraceKind
    detail: str
    at_ns: int


_DEFAULT_CAPACITY = 256
_lock = threading.Lock()
_enabled = False
_capacity = _DEFAULT_CAPACITY
_ring: deque[LoopCompatTraceEntry] = deque(maxlen=_DEFAULT_CAPACITY)


def set_loop_compat_trace_enabled(value: bool, *, capacity: int | None = None) -> None:
    global _enabled, _capacity, _ring
    with _lock:
        _enabled = value
        if capacity is not None:
            _capacity = capacity
            _ring = deque(_ring, maxlen=capacity)
        if not value:
            _ring.clear()


def is_loop_compat_trace_enabled() -> bool:
    with _lock:
        return _enabled


def record_loop_compat_trace(kind: LoopCompatTraceKind, detail: str) -> None:
    with _lock:
        if not _enabled:
            return
        _ring.append(
            LoopCompatTraceEntry(kind=kind, detail=detail, at_ns=time.monotonic_ns()),
        )


def get_loop_compat_trace() -> tuple[LoopCompatTraceEntry, ...]:
    with _lock:
        return tuple(_ring)


def clear_loop_compat_trace() -> None:
    with _lock:
        _ring.clear()


def loop_compat_trace_capacity() -> int:
    with _lock:
        return _capacity
