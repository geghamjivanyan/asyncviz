"""Per-sampler backpressure aggregator.

Mirror of the format/loader/control backpressure guards: bounded
drop-oldest queue + windowed overflow counter."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from asyncviz.runtime.sampling.models.sampling_decision import SamplingDecision


@dataclass(slots=True)
class SamplingQueueStats:
    capacity: int
    depth: int
    accepted: int
    dropped_oldest: int


class SamplingQueue:
    """Bounded drop-oldest queue for buffered decisions (used by
    the recorder when it can't keep up with the sampler)."""

    __slots__ = (
        "_accepted",
        "_buf",
        "_capacity",
        "_dropped",
        "_lock",
    )

    def __init__(self, capacity: int = 4096) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._buf: deque[SamplingDecision] = deque()
        self._lock = threading.Lock()
        self._accepted = 0
        self._dropped = 0

    def offer(self, decision: SamplingDecision) -> SamplingDecision | None:
        with self._lock:
            evicted: SamplingDecision | None = None
            if len(self._buf) >= self._capacity:
                evicted = self._buf.popleft()
                self._dropped += 1
            self._buf.append(decision)
            self._accepted += 1
            return evicted

    def drain(self) -> list[SamplingDecision]:
        with self._lock:
            items = list(self._buf)
            self._buf.clear()
            return items

    def stats(self) -> SamplingQueueStats:
        with self._lock:
            return SamplingQueueStats(
                capacity=self._capacity,
                depth=len(self._buf),
                accepted=self._accepted,
                dropped_oldest=self._dropped,
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)


@dataclass(slots=True)
class OverflowSampler:
    """Time-windowed overflow detector — same shape as other
    backpressure samplers in the codebase."""

    window_seconds: float = 1.0
    threshold: int = 16
    _count: int = 0
    _window_start: float = 0.0

    def trip(self) -> bool:
        now = time.monotonic()
        if now - self._window_start > self.window_seconds:
            self._window_start = now
            self._count = 0
        self._count += 1
        return self._count >= self.threshold

    def reset(self) -> None:
        self._count = 0
        self._window_start = 0.0
