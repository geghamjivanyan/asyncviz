"""Bounded ring-buffer tracer for executor instrumentation."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

ExecutorTraceKind = Literal[
    "executor-registered",
    "executor-finalized",
    "work-submitted",
    "work-started",
    "work-completed",
    "work-failed",
    "work-cancelled",
    "recursion-skip",
    "suppressed",
    "event-dropped",
]


@dataclass(frozen=True, slots=True)
class ExecutorTraceEntry:
    kind: ExecutorTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[ExecutorTraceEntry] = deque(maxlen=_CAPACITY)


def is_executor_trace_enabled() -> bool:
    return _enabled


def set_executor_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_executor_trace(kind: ExecutorTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(
        ExecutorTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()),
    )


def get_executor_trace() -> tuple[ExecutorTraceEntry, ...]:
    return tuple(_ring)


def clear_executor_trace() -> None:
    _ring.clear()
