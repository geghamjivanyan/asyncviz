"""Process-wide counters for the browser launcher.

Singleton — same pattern as the other CLI / runtime observability
modules. The diagnostics endpoint folds the snapshot into its
payload; tests reset between assertions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BrowserMetricsSnapshot:
    launches_attempted: int
    launches_opened: int
    launches_skipped: int
    launches_failed: int
    launches_throttled: int
    launches_deduped: int
    readiness_waits: int
    readiness_timeouts: int
    last_readiness_seconds: float
    average_readiness_seconds: float
    peak_in_flight: int


class _BrowserMetrics:
    def __init__(self) -> None:
        self._attempted = 0
        self._opened = 0
        self._skipped = 0
        self._failed = 0
        self._throttled = 0
        self._deduped = 0
        self._readiness_waits = 0
        self._readiness_timeouts = 0
        self._readiness_total = 0.0
        self._readiness_last = 0.0
        self._peak_in_flight = 0

    def record_attempt(self) -> None:
        self._attempted += 1

    def record_opened(self) -> None:
        self._opened += 1

    def record_skipped(self) -> None:
        self._skipped += 1

    def record_failed(self) -> None:
        self._failed += 1

    def record_throttled(self) -> None:
        self._throttled += 1

    def record_deduped(self) -> None:
        self._deduped += 1

    def record_readiness(self, *, elapsed_seconds: float, timed_out: bool) -> None:
        self._readiness_waits += 1
        if timed_out:
            self._readiness_timeouts += 1
        if elapsed_seconds >= 0:
            self._readiness_total += elapsed_seconds
            self._readiness_last = elapsed_seconds

    def record_peak_in_flight(self, value: int) -> None:
        if value > self._peak_in_flight:
            self._peak_in_flight = value

    def snapshot(self) -> BrowserMetricsSnapshot:
        avg = self._readiness_total / self._readiness_waits if self._readiness_waits else 0.0
        return BrowserMetricsSnapshot(
            launches_attempted=self._attempted,
            launches_opened=self._opened,
            launches_skipped=self._skipped,
            launches_failed=self._failed,
            launches_throttled=self._throttled,
            launches_deduped=self._deduped,
            readiness_waits=self._readiness_waits,
            readiness_timeouts=self._readiness_timeouts,
            last_readiness_seconds=self._readiness_last,
            average_readiness_seconds=avg,
            peak_in_flight=self._peak_in_flight,
        )

    def reset(self) -> None:
        self.__init__()


_instance = _BrowserMetrics()


def get_browser_metrics() -> _BrowserMetrics:
    return _instance


def reset_browser_metrics() -> None:
    _instance.reset()
