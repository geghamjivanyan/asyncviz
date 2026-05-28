"""Bounded-growth thresholds + breach signaling.

Watches the memory-optimizer counters + raises a structured
:class:`MemoryThresholdBreach` when a sustained-growth metric
crosses a configured cap. The breach is informational — callers
typically use it to trigger an eviction sweep, not to crash.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryThresholdBreach:
    """One observed breach."""

    metric_name: str
    observed: int
    threshold: int


BreachListener = Callable[[MemoryThresholdBreach], None]


class MemoryThresholdMonitor:
    """Process-wide threshold registry."""

    __slots__ = ("_breach_count", "_listeners", "_lock", "_thresholds")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thresholds: dict[str, int] = {}
        self._listeners: list[BreachListener] = []
        self._breach_count = 0

    def set_threshold(self, metric_name: str, threshold: int) -> None:
        with self._lock:
            self._thresholds[metric_name] = threshold

    def remove_threshold(self, metric_name: str) -> None:
        with self._lock:
            self._thresholds.pop(metric_name, None)

    def threshold(self, metric_name: str) -> int | None:
        with self._lock:
            return self._thresholds.get(metric_name)

    def observe(self, metric_name: str, observed: int) -> MemoryThresholdBreach | None:
        with self._lock:
            threshold = self._thresholds.get(metric_name)
            if threshold is None or observed <= threshold:
                return None
            self._breach_count += 1
            breach = MemoryThresholdBreach(
                metric_name=metric_name,
                observed=observed,
                threshold=threshold,
            )
            listeners = tuple(self._listeners)
        for listener in listeners:
            # Isolate listener faults so a buggy subscriber can't
            # break the monitor.
            with contextlib.suppress(Exception):
                listener(breach)
        return breach

    def subscribe(self, listener: BreachListener) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return _unsubscribe

    @property
    def breach_count(self) -> int:
        with self._lock:
            return self._breach_count

    def reset(self) -> None:
        with self._lock:
            self._thresholds.clear()
            self._listeners.clear()
            self._breach_count = 0
