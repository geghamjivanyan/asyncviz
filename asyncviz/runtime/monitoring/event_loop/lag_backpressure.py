"""Self-protection policy for the lag monitor.

Two distinct concerns:

* **Sample drops** — the asyncio sleep was so late it overshot the next
  deadline by more than one full interval. Accounted for separately from
  threshold hits so the operator can tell "the monitor missed a sample"
  apart from "the loop was blocked at this sample."
* **Event backpressure** — the monitor emits events through a callback
  (typically the bus). When the consumer can't keep up, the monitor
  drops new events rather than enqueueing forever. This stops the
  monitor itself from amplifying lag.

The policy is intentionally tiny — both decisions are made from
counters held on :class:`LagMonitorBackpressure`. No allocation, no
locking beyond a single int update.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackpressureDecision:
    """The outcome of a single backpressure check.

    ``accepted`` is the only consumer-relevant field — ``reason`` is
    diagnostic. Frozen so the hot path can stash it in a local without
    worrying about aliasing.
    """

    accepted: bool
    reason: str
    pending: int
    capacity: int


class LagMonitorBackpressure:
    """Bounded counter for in-flight monitor events.

    The monitor increments :meth:`acquire` before publishing an event
    and calls :meth:`release` once the publish completes. When the
    in-flight count would exceed ``capacity``, :meth:`acquire` denies
    and the caller drops the event. ``capacity == 0`` disables the
    cap (every acquire accepts).
    """

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

    def acquire(self) -> BackpressureDecision:
        with self._lock:
            if self._capacity == 0:
                self._pending += 1
                return BackpressureDecision(
                    accepted=True,
                    reason="uncapped",
                    pending=self._pending,
                    capacity=self._capacity,
                )
            if self._pending >= self._capacity:
                self._denied += 1
                return BackpressureDecision(
                    accepted=False,
                    reason="capacity_exceeded",
                    pending=self._pending,
                    capacity=self._capacity,
                )
            self._pending += 1
            return BackpressureDecision(
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
