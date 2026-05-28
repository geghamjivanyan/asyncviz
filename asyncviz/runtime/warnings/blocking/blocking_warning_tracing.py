"""Opt-in trace ring for the blocking warning emitter."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Literal

TraceKind = Literal[
    "opened",
    "escalated",
    "active",
    "recovered",
    "expired",
    "suppressed_policy",
    "suppressed_dedup",
    "capture_correlated",
    "capture_uncorrelated",
    "backpressure_denied",
    "emitter_failure",
    "listener_failure",
    "reconfigure",
]


@dataclass(frozen=True, slots=True)
class BlockingWarningTraceRecord:
    kind: TraceKind
    monotonic_ns: int
    detail: str
    group_id: str | None = None
    transition: str | None = None
    severity: str | None = None


class BlockingWarningTracer:
    DEFAULT_CAPACITY: int = 256

    def __init__(self, *, capacity: int = DEFAULT_CAPACITY, enabled: bool = False) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0 (got {capacity})")
        self._lock = threading.Lock()
        self._capacity = capacity
        self._enabled = enabled
        self._records: deque[BlockingWarningTraceRecord] = deque(maxlen=capacity)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def capacity(self) -> int:
        return self._capacity

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def record(self, record: BlockingWarningTraceRecord) -> None:
        if not self._enabled:
            return
        with self._lock:
            self._records.append(record)

    def snapshot(self) -> tuple[BlockingWarningTraceRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
