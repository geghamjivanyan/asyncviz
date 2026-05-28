"""Integration-suite trace ring buffer."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

IntegrationTraceKind = Literal[
    "scenario-started",
    "scenario-completed",
    "scenario-errored",
    "determinism-run",
    "uvloop-run",
    "violation",
    "diagnostic",
]


@dataclass(frozen=True, slots=True)
class IntegrationTraceEntry:
    kind: IntegrationTraceKind
    detail: str
    at_ns: int


_DEFAULT_CAPACITY = 256
_lock = threading.Lock()
_enabled = False
_capacity = _DEFAULT_CAPACITY
_ring: deque[IntegrationTraceEntry] = deque(maxlen=_DEFAULT_CAPACITY)


def set_integration_trace_enabled(value: bool, *, capacity: int | None = None) -> None:
    global _enabled, _capacity, _ring
    with _lock:
        _enabled = value
        if capacity is not None:
            _capacity = capacity
            _ring = deque(_ring, maxlen=capacity)
        if not value:
            _ring.clear()


def is_integration_trace_enabled() -> bool:
    with _lock:
        return _enabled


def record_integration_trace(kind: IntegrationTraceKind, detail: str) -> None:
    with _lock:
        if not _enabled:
            return
        _ring.append(
            IntegrationTraceEntry(kind=kind, detail=detail, at_ns=time.monotonic_ns()),
        )


def get_integration_trace() -> tuple[IntegrationTraceEntry, ...]:
    with _lock:
        return tuple(_ring)


def clear_integration_trace() -> None:
    with _lock:
        _ring.clear()


def integration_trace_capacity() -> int:
    with _lock:
        return _capacity
