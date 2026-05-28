"""Opt-in trace ring for debugging scheduler / sampler behavior.

Disabled by default. When :attr:`LagConfiguration.trace_enabled` is on,
the monitor pushes a :class:`LagTraceRecord` into a small ring per
sample. The dashboard's debug endpoint can inspect the ring to
reconstruct scheduler timing without re-running the workload.

Production code paths must never call here directly — they go through
:class:`LagDiagnostics`, which checks the configuration flag.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class LagTraceRecord:
    """One trace entry from the monitor's sampling cadence.

    ``kind`` is a short string discriminator. Fields beyond the kind +
    timing are optional — different kinds populate different subsets.
    """

    kind: Literal[
        "sample",
        "drop",
        "scheduler_drift",
        "threshold_breach",
        "backpressure_denied",
        "sampler_failure",
        "reconfigure",
    ]
    sample_index: int
    monotonic_ns: int
    detail: str
    lag_ns: int = 0


class LagTracer:
    """Bounded ring for :class:`LagTraceRecord`.

    Thread-safe. Reads (snapshot) copy out the current contents; writes
    are O(1) deque appends.
    """

    DEFAULT_CAPACITY: int = 256

    def __init__(self, *, capacity: int = DEFAULT_CAPACITY, enabled: bool = False) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0 (got {capacity})")
        self._lock = threading.Lock()
        self._records: deque[LagTraceRecord] = deque(maxlen=capacity)
        self._capacity = capacity
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @property
    def capacity(self) -> int:
        return self._capacity

    def record(self, record: LagTraceRecord) -> None:
        if not self._enabled:
            return
        with self._lock:
            self._records.append(record)

    def snapshot(self) -> tuple[LagTraceRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
