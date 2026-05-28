"""Per-executor utilization tracker.

Tracks the *current* active-worker count by reacting to
``work.started`` (+1) and ``work.completed`` / ``work.failed`` /
``work.cancelled`` (-1). The window in
:mod:`executor_metrics_windows` snapshots samples over time for the
rolling mean.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.instrumentation.executor.metrics.executor_metrics_models import (
    ExecutorUtilizationSnapshot,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_windows import (
    UtilizationWindow,
)


@dataclass(slots=True)
class UtilizationTracker:
    window: UtilizationWindow
    max_workers: int | None = None
    active_workers: int = 0

    def increment(self) -> None:
        self.active_workers += 1
        self.window.observe(self.active_workers)

    def decrement(self) -> None:
        if self.active_workers > 0:
            self.active_workers -= 1
        self.window.observe(self.active_workers)

    def update_max_workers(self, max_workers: int | None) -> None:
        if max_workers is not None and max_workers > 0:
            self.max_workers = max_workers

    def snapshot(self) -> ExecutorUtilizationSnapshot:
        ratio = 0.0
        mean = 0.0
        if self.max_workers and self.max_workers > 0:
            ratio = min(1.0, self.active_workers / self.max_workers)
            mean = min(1.0, self.window.mean() / self.max_workers)
        return ExecutorUtilizationSnapshot(
            active_workers=self.active_workers,
            peak_active_workers=self.window.peak,
            max_workers=self.max_workers,
            utilization_ratio=ratio,
            mean_utilization=mean,
            sample_count=len(self.window.samples),
        )

    def reset(self) -> None:
        self.active_workers = 0
        self.window.reset()
