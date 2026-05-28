"""Ring-buffer tracer for the browser launcher.

Disabled by default — the diagnostics page / ``asyncviz doctor``
flip it on for live inspection. Same shape as the other ring-buffer
tracers in the codebase.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

_CAPACITY = 256

BrowserTraceKind = Literal[
    "launch-attempt",
    "launch-opened",
    "launch-skipped",
    "launch-failed",
    "launch-throttled",
    "launch-deduped",
    "readiness-start",
    "readiness-success",
    "readiness-timeout",
    "policy-resolved",
]


@dataclass(frozen=True, slots=True)
class BrowserTraceEntry:
    kind: BrowserTraceKind
    detail: str
    at_monotonic: float


_enabled = False
_ring: deque[BrowserTraceEntry] = deque(maxlen=_CAPACITY)


def is_browser_trace_enabled() -> bool:
    return _enabled


def set_browser_trace_enabled(value: bool) -> None:
    global _enabled
    _enabled = value
    if not value:
        _ring.clear()


def record_browser_trace(kind: BrowserTraceKind, detail: str = "") -> None:
    if not _enabled:
        return
    _ring.append(BrowserTraceEntry(kind=kind, detail=detail, at_monotonic=time.monotonic()))


def get_browser_trace() -> tuple[BrowserTraceEntry, ...]:
    return tuple(_ring)


def clear_browser_trace() -> None:
    _ring.clear()
