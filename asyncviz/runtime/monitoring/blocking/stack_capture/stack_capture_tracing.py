"""Opt-in trace ring for the stack-capture engine."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Literal

TraceKind = Literal[
    "capture",
    "skip_policy",
    "skip_reentry",
    "sampler_failure",
    "serializer_failure",
    "emitter_failure",
    "backpressure_denied",
    "trim",
    "reconfigure",
]


@dataclass(frozen=True, slots=True)
class StackCaptureTraceRecord:
    kind: TraceKind
    monotonic_ns: int
    detail: str
    capture_id: int = -1
    window_id: str | None = None


class StackCaptureTracer:
    DEFAULT_CAPACITY: int = 256

    def __init__(self, *, capacity: int = DEFAULT_CAPACITY, enabled: bool = False) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0 (got {capacity})")
        self._lock = threading.Lock()
        self._capacity = capacity
        self._enabled = enabled
        self._records: deque[StackCaptureTraceRecord] = deque(maxlen=capacity)

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

    def record(self, record: StackCaptureTraceRecord) -> None:
        if not self._enabled:
            return
        with self._lock:
            self._records.append(record)

    def snapshot(self) -> tuple[StackCaptureTraceRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
