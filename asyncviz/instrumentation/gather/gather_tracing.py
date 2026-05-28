"""Bounded ring-buffer tracer for gather instrumentation.

Off by default. Toggle via :func:`set_gather_trace_enabled` to chase
patch-lifecycle or dependency-tracking bugs during development.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

GatherTraceKind = Literal[
    "gather-registered",
    "gather-finalized",
    "gather-created",
    "gather-child-attached",
    "gather-wait-started",
    "gather-child-completed",
    "gather-completed",
    "gather-cancelled",
    "gather-failed",
    "recursion-skip",
    "suppressed",
    "event-dropped",
]


@dataclass(frozen=True, slots=True)
class GatherTraceEntry:
    kind: GatherTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[GatherTraceEntry] = deque(maxlen=_CAPACITY)


def is_gather_trace_enabled() -> bool:
    return _enabled


def set_gather_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_gather_trace(kind: GatherTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(
        GatherTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()),
    )


def get_gather_trace() -> tuple[GatherTraceEntry, ...]:
    return tuple(_ring)


def clear_gather_trace() -> None:
    _ring.clear()
