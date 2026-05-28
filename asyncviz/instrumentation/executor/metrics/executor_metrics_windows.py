"""Bounded rolling utilization window for a single executor."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class UtilizationWindow:
    capacity: int
    peak: int = 0
    samples: deque[int] = field(default_factory=lambda: deque())
    _sum: int = 0

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError(f"capacity must be >= 1 (got {self.capacity})")
        self.samples = deque(maxlen=self.capacity)

    def observe(self, active: int) -> None:
        if active < 0:
            active = 0
        if active > self.peak:
            self.peak = active
        if len(self.samples) == self.capacity:
            self._sum -= self.samples[0]
        self.samples.append(active)
        self._sum += active

    def mean(self) -> float:
        return self._sum / len(self.samples) if self.samples else 0.0

    def reset(self) -> None:
        self.peak = 0
        self._sum = 0
        self.samples.clear()
