"""Memory-side backpressure primitive.

The memory optimizer's hot paths are guarded by a single overflow
sampler that aggregates breach events into bounded time windows so
a one-off spike doesn't trip a corrective response, while a
sustained burst does.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(slots=True)
class MemoryOverflowSampler:
    """Time-windowed overflow aggregator."""

    window_seconds: float = 1.0
    threshold: int = 16
    _count: int = 0
    _window_start: float = 0.0
    _lock: threading.Lock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._lock is None:
            self._lock = threading.Lock()

    def trip(self) -> bool:
        """Record one overflow event. Returns True if the rolling
        window's count crossed the threshold."""
        now = time.monotonic()
        with self._lock:
            if now - self._window_start > self.window_seconds:
                self._window_start = now
                self._count = 0
            self._count += 1
            return self._count >= self.threshold

    def reset(self) -> None:
        with self._lock:
            self._count = 0
            self._window_start = 0.0
