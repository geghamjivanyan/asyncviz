"""Rolling-window rate meter (events / second).

Buckets observations into 1-second windows; ``rate`` is the sum of the
last ``window_seconds`` buckets divided by ``window_seconds``.
The bucket count is bounded so memory stays flat under steady-state load.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateSnapshot:
    """Immutable view of a :class:`RateMeter`."""

    rate_per_second: float
    total_observations: int
    window_seconds: int


class RateMeter:
    """Threadsafe sliding-window rate calculator.

    Time is supplied by the caller as a monotonic float-seconds reading —
    the meter is decoupled from any specific clock so tests can drive it
    with virtual time.
    """

    __slots__ = ("_buckets", "_current_bucket_start", "_lock", "_total", "_window")

    def __init__(self, *, window_seconds: int = 30) -> None:
        if window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")
        self._lock = threading.Lock()
        self._window = window_seconds
        self._buckets: deque[int] = deque(maxlen=window_seconds)
        self._current_bucket_start: int | None = None
        self._total = 0

    def observe(self, *, monotonic_seconds: float, count: int = 1) -> None:
        with self._lock:
            second = int(monotonic_seconds)
            if self._current_bucket_start is None:
                self._current_bucket_start = second
                self._buckets.append(0)
            elif second > self._current_bucket_start:
                # Pad with zero buckets for any silent windows between the
                # last observation and ``second``.
                gap = second - self._current_bucket_start
                if gap >= self._window:
                    self._buckets.clear()
                    self._buckets.append(0)
                else:
                    for _ in range(gap):
                        self._buckets.append(0)
                self._current_bucket_start = second
            # Add to the most-recent bucket (the head of the right edge).
            self._buckets[-1] += count
            self._total += count

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
            self._current_bucket_start = None
            self._total = 0

    def snapshot(self, *, monotonic_seconds: float | None = None) -> RateSnapshot:
        with self._lock:
            # Advance virtual time to ``monotonic_seconds`` so an idle window
            # decays correctly even if no observation has fired recently.
            if monotonic_seconds is not None and self._current_bucket_start is not None:
                second = int(monotonic_seconds)
                if second > self._current_bucket_start:
                    gap = second - self._current_bucket_start
                    if gap >= self._window:
                        self._buckets.clear()
                    else:
                        for _ in range(gap):
                            self._buckets.append(0)
                    self._current_bucket_start = second
            window_total = sum(self._buckets)
            rate = window_total / self._window if self._window else 0.0
            return RateSnapshot(
                rate_per_second=rate,
                total_observations=self._total,
                window_seconds=self._window,
            )
