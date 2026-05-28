"""Bounded trace ring for replay-format lifecycle events.

Cheap, in-process, off by default. When enabled, every codec / reader
operation pushes a small entry into a 256-deep ring so the diagnostics
page can show what just happened without scraping logs. The ring is
the *only* place this module retains state, so disabling tracing
costs nothing on the hot path beyond an attribute read.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Final, Literal

NdjsonTraceKind = Literal[
    "frame-encoded",
    "frame-decoded",
    "frame-skipped",
    "validation-failed",
    "integrity-failed",
    "migration-applied",
    "schema-skew",
    "recovery-recovered",
    "recovery-discarded",
    "stream-opened",
    "stream-closed",
    "backpressure",
]

_TRACE_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class NdjsonTraceEntry:
    """One ring entry. Tiny on purpose — diagnostic, not audit."""

    monotonic_ns: int
    kind: NdjsonTraceKind
    detail: str


class _TraceRing:
    """Bounded ring of trace entries."""

    __slots__ = ("_entries", "_lock")

    def __init__(self) -> None:
        self._entries: deque[NdjsonTraceEntry] = deque(maxlen=_TRACE_CAPACITY)
        self._lock = threading.Lock()

    def push(self, entry: NdjsonTraceEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> tuple[NdjsonTraceEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_RING: _TraceRing = _TraceRing()
_enabled: bool = False


def set_ndjson_trace_enabled(value: bool) -> None:
    """Toggle tracing. Disabled writers cost a single attribute load."""
    global _enabled
    _enabled = value
    if not value:
        _RING.clear()


def is_ndjson_trace_enabled() -> bool:
    return _enabled


def record_ndjson_trace(kind: NdjsonTraceKind, detail: str = "") -> None:
    """Append a trace entry if tracing is enabled."""
    if not _enabled:
        return
    _RING.push(NdjsonTraceEntry(monotonic_ns=time.monotonic_ns(), kind=kind, detail=detail))


def get_ndjson_trace() -> tuple[NdjsonTraceEntry, ...]:
    return _RING.snapshot()


def clear_ndjson_trace() -> None:
    _RING.clear()
