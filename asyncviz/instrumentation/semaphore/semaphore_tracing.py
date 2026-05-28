"""Ring-buffer tracer for semaphore instrumentation.

Disabled by default. Switch on via
:func:`set_semaphore_trace_enabled` to debug acquire/release ordering
or contention edge detection during development. Bounded so leaving
it on in production wouldn't grow memory — though the per-event cost
is non-zero, so keep it off there.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

SemaphoreTraceKind = Literal[
    "semaphore-registered",
    "semaphore-finalized",
    "semaphore-acquire-started",
    "semaphore-acquired",
    "semaphore-released",
    "semaphore-cancelled",
    "semaphore-contention",
    "recursion-skip",
    "event-dropped",
]


@dataclass(frozen=True, slots=True)
class SemaphoreTraceEntry:
    kind: SemaphoreTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[SemaphoreTraceEntry] = deque(maxlen=_CAPACITY)


def is_semaphore_trace_enabled() -> bool:
    return _enabled


def set_semaphore_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_semaphore_trace(kind: SemaphoreTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(
        SemaphoreTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()),
    )


def get_semaphore_trace() -> tuple[SemaphoreTraceEntry, ...]:
    return tuple(_ring)


def clear_semaphore_trace() -> None:
    _ring.clear()
