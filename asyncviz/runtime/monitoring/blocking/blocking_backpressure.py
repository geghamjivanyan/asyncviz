"""Bounded in-flight counter for blocking-detector emissions.

Mirrors :class:`LagMonitorBackpressure` but lives in its own module
so the detector and the lag monitor can be tuned independently. The
contract is identical: acquire/release pairs, capacity 0 = uncapped,
denied counter for self-observability.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BlockingBackpressureDecision:
    accepted: bool
    reason: str
    pending: int
    capacity: int


class BlockingDetectorBackpressure:
    __slots__ = ("_capacity", "_denied", "_lock", "_pending")

    def __init__(self, *, capacity: int) -> None:
        if capacity < 0:
            raise ValueError(f"capacity must be >= 0 (got {capacity})")
        self._capacity = capacity
        self._pending = 0
        self._denied = 0
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def pending(self) -> int:
        with self._lock:
            return self._pending

    @property
    def denied(self) -> int:
        with self._lock:
            return self._denied

    def acquire(self) -> BlockingBackpressureDecision:
        with self._lock:
            if self._capacity == 0:
                self._pending += 1
                return BlockingBackpressureDecision(
                    accepted=True,
                    reason="uncapped",
                    pending=self._pending,
                    capacity=self._capacity,
                )
            if self._pending >= self._capacity:
                self._denied += 1
                return BlockingBackpressureDecision(
                    accepted=False,
                    reason="capacity_exceeded",
                    pending=self._pending,
                    capacity=self._capacity,
                )
            self._pending += 1
            return BlockingBackpressureDecision(
                accepted=True,
                reason="accepted",
                pending=self._pending,
                capacity=self._capacity,
            )

    def release(self) -> None:
        with self._lock:
            if self._pending > 0:
                self._pending -= 1

    def reset(self) -> None:
        with self._lock:
            self._pending = 0
            self._denied = 0
