"""Deterministic monotonic-clock fake for tests.

Tests inject this through :class:`EventLoopLagMonitor`'s
``monotonic_clock`` parameter to drive the sampler / statistics /
threshold paths without relying on wall time.

Pure synchronous: tests advance the clock manually and call the
sampler / monitor's ``apply_measurement`` directly. The asyncio
scheduler path is exercised separately with the real clock + short
intervals.
"""

from __future__ import annotations

import threading


class FakeMonotonicClock:
    """Caller-driven monotonic clock.

    Starts at ``initial_ns`` (default 0). :meth:`advance` moves time
    forward; :meth:`set_to` jumps to an exact value (must be
    non-decreasing). :meth:`monotonic_ns` reads the current value.

    Thread-safe — tests sometimes touch the clock from a callback fired
    on the dispatch loop while asserting on the main thread.
    """

    __slots__ = ("_lock", "_now_ns")

    def __init__(self, *, initial_ns: int = 0) -> None:
        if initial_ns < 0:
            raise ValueError(f"initial_ns must be >= 0 (got {initial_ns})")
        self._lock = threading.Lock()
        self._now_ns = initial_ns

    def monotonic_ns(self) -> int:
        with self._lock:
            return self._now_ns

    def advance(self, delta_ns: int) -> int:
        if delta_ns < 0:
            raise ValueError(f"advance delta must be >= 0 (got {delta_ns})")
        with self._lock:
            self._now_ns += delta_ns
            return self._now_ns

    def set_to(self, value_ns: int) -> None:
        with self._lock:
            if value_ns < self._now_ns:
                raise ValueError(
                    f"set_to value must be non-decreasing (got {value_ns}, current {self._now_ns})"
                )
            self._now_ns = value_ns
