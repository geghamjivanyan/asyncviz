"""Stress-runner trace ring buffer.

Disabled by default. When enabled, records scenario lifecycle,
threshold violations, failure injections, and observed signals.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

StressTraceKind = Literal[
    "scenario-started",
    "scenario-completed",
    "scenario-errored",
    "signal",
    "violation",
    "failure-injected",
    "diagnostic",
]


@dataclass(frozen=True, slots=True)
class StressTraceEntry:
    kind: StressTraceKind
    detail: str
    at_ns: int


_DEFAULT_CAPACITY = 256
_lock = threading.Lock()
_enabled = False
_ring: deque[StressTraceEntry] = deque(maxlen=_DEFAULT_CAPACITY)
_capacity = _DEFAULT_CAPACITY


def set_stress_trace_enabled(value: bool, *, capacity: int | None = None) -> None:
    """Toggle tracing. Optionally resize the ring at the same time."""
    global _enabled, _capacity, _ring
    with _lock:
        _enabled = value
        if capacity is not None:
            _capacity = capacity
            _ring = deque(_ring, maxlen=capacity)
        if not value:
            _ring.clear()


def is_stress_trace_enabled() -> bool:
    with _lock:
        return _enabled


def record_stress_trace(kind: StressTraceKind, detail: str) -> None:
    with _lock:
        if not _enabled:
            return
        _ring.append(
            StressTraceEntry(kind=kind, detail=detail, at_ns=time.monotonic_ns()),
        )


def get_stress_trace() -> tuple[StressTraceEntry, ...]:
    with _lock:
        return tuple(_ring)


def clear_stress_trace() -> None:
    with _lock:
        _ring.clear()


def stress_trace_capacity() -> int:
    with _lock:
        return _capacity
