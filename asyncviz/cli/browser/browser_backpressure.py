"""Bounded concurrency for browser launches.

A user running 10 ``asyncviz run`` instances back-to-back shouldn't
fork 10 simultaneous browser opens. This semaphore caps the number
of in-flight launches; new launches above the cap fail immediately
with a structured outcome so the launcher can report the skip.

Default cap is 4 — generous for normal use, defensive enough to
catch runaway scripts.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

DEFAULT_MAX_CONCURRENT_LAUNCHES: int = 4


@dataclass(slots=True)
class BrowserBackpressureGuard:
    """Bounded in-flight counter."""

    max_concurrent: int = DEFAULT_MAX_CONCURRENT_LAUNCHES
    _in_flight: int = 0
    _peak: int = 0
    _denied: int = 0
    _lock: threading.Lock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.max_concurrent < 1:
            raise ValueError(
                f"max_concurrent must be ≥ 1, got {self.max_concurrent}",
            )
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """Try to reserve a slot. ``True`` on success."""
        with self._lock:
            if self._in_flight >= self.max_concurrent:
                self._denied += 1
                return False
            self._in_flight += 1
            if self._in_flight > self._peak:
                self._peak = self._in_flight
            return True

    def release(self) -> None:
        with self._lock:
            if self._in_flight > 0:
                self._in_flight -= 1

    @property
    def in_flight(self) -> int:
        with self._lock:
            return self._in_flight

    @property
    def peak(self) -> int:
        with self._lock:
            return self._peak

    @property
    def denied(self) -> int:
        with self._lock:
            return self._denied


_default_guard = BrowserBackpressureGuard()


def get_default_backpressure_guard() -> BrowserBackpressureGuard:
    return _default_guard


def reset_default_backpressure_guard() -> None:
    global _default_guard
    _default_guard = BrowserBackpressureGuard()
