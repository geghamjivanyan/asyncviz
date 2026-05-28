"""Ring-buffer tracer for the env loader.

Disabled by default — the diagnostics page flips it on for live
inspection. Mirrors the other tracing modules in the codebase.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

EnvironmentTraceKind = Literal[
    "load-start",
    "key-parsed",
    "key-failed",
    "key-skipped",
    "override-applied",
    "redacted",
    "load-finished",
]


@dataclass(frozen=True, slots=True)
class EnvironmentTraceEntry:
    kind: EnvironmentTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[EnvironmentTraceEntry] = deque(maxlen=_CAPACITY)


def is_environment_trace_enabled() -> bool:
    return _enabled


def set_environment_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_environment_trace(kind: EnvironmentTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(
        EnvironmentTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()),
    )


def get_environment_trace() -> tuple[EnvironmentTraceEntry, ...]:
    return tuple(_ring)


def clear_environment_trace() -> None:
    _ring.clear()
