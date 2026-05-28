"""Opt-in trace ring for debugging the blocking detector.

Disabled by default. When enabled via
:attr:`BlockingDetectorConfiguration.trace_enabled`, the detector
pushes a :class:`BlockingTraceRecord` for every interesting transition
(classification, escalation, window open/extend/close, cooldown
suppression). The dashboard's debug endpoint inspects the ring to
reconstruct detector decisions post-hoc.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Literal

TraceKind = Literal[
    "classify",
    "escalate",
    "window_open",
    "window_extend",
    "window_close",
    "cooldown_suppress",
    "backpressure_denied",
    "handler_failure",
    "reconfigure",
]


@dataclass(frozen=True, slots=True)
class BlockingTraceRecord:
    kind: TraceKind
    sample_index: int
    monotonic_ns: int
    detail: str
    severity: str = ""
    lag_ns: int = 0


class BlockingTracer:
    DEFAULT_CAPACITY: int = 256

    def __init__(self, *, capacity: int = DEFAULT_CAPACITY, enabled: bool = False) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0 (got {capacity})")
        self._lock = threading.Lock()
        self._records: deque[BlockingTraceRecord] = deque(maxlen=capacity)
        self._capacity = capacity
        self._enabled = enabled

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

    def record(self, record: BlockingTraceRecord) -> None:
        if not self._enabled:
            return
        with self._lock:
            self._records.append(record)

    def snapshot(self) -> tuple[BlockingTraceRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
