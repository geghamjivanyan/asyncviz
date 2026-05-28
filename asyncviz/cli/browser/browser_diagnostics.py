"""Diagnostics snapshot for the browser launcher subsystem.

Combines the metrics + trace + last-launch view into a single record
that the diagnostics endpoint / ``asyncviz doctor`` can surface.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass

from asyncviz.cli.browser.browser_backpressure import (
    get_default_backpressure_guard,
)
from asyncviz.cli.browser.browser_metrics import (
    BrowserMetricsSnapshot,
    get_browser_metrics,
)
from asyncviz.cli.browser.browser_statistics import LaunchStatistics
from asyncviz.cli.browser.browser_tracing import (
    BrowserTraceEntry,
    get_browser_trace,
    is_browser_trace_enabled,
)

_lock = threading.Lock()
_last_launch: LaunchStatistics | None = None


def record_last_launch(stats: LaunchStatistics) -> None:
    """Stash ``stats`` so diagnostics can inspect the most-recent attempt."""
    global _last_launch
    with _lock:
        _last_launch = stats


def get_last_launch() -> LaunchStatistics | None:
    with _lock:
        return _last_launch


def reset_last_launch() -> None:
    global _last_launch
    with _lock:
        _last_launch = None


@dataclass(frozen=True, slots=True)
class BrowserDiagnosticsSnapshot:
    """Composed diagnostics view consumed by the diagnostics endpoint."""

    metrics: BrowserMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[BrowserTraceEntry, ...]
    backpressure_in_flight: int
    backpressure_peak: int
    backpressure_denied: int
    last_launch: LaunchStatistics | None

    def to_dict(self) -> dict[str, object]:
        return {
            "metrics": asdict(self.metrics),
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [asdict(entry) for entry in self.recent_trace],
            "backpressure": {
                "in_flight": self.backpressure_in_flight,
                "peak": self.backpressure_peak,
                "denied": self.backpressure_denied,
            },
            "last_launch": self.last_launch.to_dict() if self.last_launch else None,
        }


def build_browser_diagnostics(*, tail: int = 16) -> BrowserDiagnosticsSnapshot:
    trace = get_browser_trace()
    guard = get_default_backpressure_guard()
    return BrowserDiagnosticsSnapshot(
        metrics=get_browser_metrics().snapshot(),
        trace_enabled=is_browser_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
        backpressure_in_flight=guard.in_flight,
        backpressure_peak=guard.peak,
        backpressure_denied=guard.denied,
        last_launch=get_last_launch(),
    )
