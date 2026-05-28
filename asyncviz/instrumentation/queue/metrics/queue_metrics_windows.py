"""Bounded rolling occupancy window for a single queue.

Holds the last ``capacity`` size samples so we can compute the rolling
mean without scanning the entire event history. ``observe`` is O(1);
``mean`` is O(N) but only called when a snapshot is requested.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class OccupancyWindow:
    capacity: int
    peak: int = 0
    samples: deque[int] = field(default_factory=lambda: deque())
    _sum: int = 0

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError(f"capacity must be >= 1 (got {self.capacity})")
        self.samples = deque(maxlen=self.capacity)

    def observe(self, size: int) -> None:
        if size < 0:
            size = 0
        if size > self.peak:
            self.peak = size
        if len(self.samples) == self.capacity:
            self._sum -= self.samples[0]
        self.samples.append(size)
        self._sum += size

    def mean(self) -> float:
        return self._sum / len(self.samples) if self.samples else 0.0

    def reset(self) -> None:
        self.peak = 0
        self._sum = 0
        self.samples.clear()
