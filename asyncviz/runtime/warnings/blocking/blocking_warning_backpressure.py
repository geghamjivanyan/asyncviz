"""Bounded in-flight counter for warning emissions.

Mirrors the monitoring backpressure modules. Kept in its own file so
the emitter can be tuned independently of the detector / capture
engine that feed it.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WarningBackpressureDecision:
    accepted: bool
    reason: str
    pending: int
    capacity: int


class WarningEmitterBackpressure:
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

    def acquire(self) -> WarningBackpressureDecision:
        with self._lock:
            if self._capacity == 0:
                self._pending += 1
                return WarningBackpressureDecision(
                    accepted=True,
                    reason="uncapped",
                    pending=self._pending,
                    capacity=self._capacity,
                )
            if self._pending >= self._capacity:
                self._denied += 1
                return WarningBackpressureDecision(
                    accepted=False,
                    reason="capacity_exceeded",
                    pending=self._pending,
                    capacity=self._capacity,
                )
            self._pending += 1
            return WarningBackpressureDecision(
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
