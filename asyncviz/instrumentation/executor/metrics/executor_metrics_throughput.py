"""Per-executor submission + completion throughput counters."""

from __future__ import annotations

from dataclasses import dataclass, field

from asyncviz.instrumentation.executor.metrics.executor_metrics_models import (
    ExecutorThroughputSnapshot,
)
from asyncviz.runtime.metrics.rates import RateMeter


@dataclass(slots=True)
class ThroughputCounters:
    window_seconds: int = 30
    submissions: int = 0
    completions: int = 0
    failures: int = 0
    cancellations: int = 0
    submission_rate: RateMeter = field(init=False)
    completion_rate: RateMeter = field(init=False)

    def __post_init__(self) -> None:
        self.submission_rate = RateMeter(window_seconds=self.window_seconds)
        self.completion_rate = RateMeter(window_seconds=self.window_seconds)

    def record_submission(self, *, monotonic_seconds: float) -> None:
        self.submissions += 1
        self.submission_rate.observe(monotonic_seconds=monotonic_seconds)

    def record_completion(self, *, monotonic_seconds: float) -> None:
        self.completions += 1
        self.completion_rate.observe(monotonic_seconds=monotonic_seconds)

    def record_failure(self, *, monotonic_seconds: float) -> None:
        self.failures += 1
        self.completion_rate.observe(monotonic_seconds=monotonic_seconds)

    def record_cancellation(self, *, monotonic_seconds: float) -> None:
        self.cancellations += 1
        self.completion_rate.observe(monotonic_seconds=monotonic_seconds)

    def snapshot(self, *, monotonic_seconds: float | None = None) -> ExecutorThroughputSnapshot:
        sub_rate = self.submission_rate.snapshot(
            monotonic_seconds=monotonic_seconds,
        ).rate_per_second
        comp_rate = self.completion_rate.snapshot(
            monotonic_seconds=monotonic_seconds,
        ).rate_per_second
        backlog = (
            self.submissions - self.completions - self.failures - self.cancellations
        )
        return ExecutorThroughputSnapshot(
            submissions=self.submissions,
            completions=self.completions,
            failures=self.failures,
            cancellations=self.cancellations,
            submission_rate=sub_rate,
            completion_rate=comp_rate,
            backlog=max(0, backlog),
        )

    def reset(self) -> None:
        self.submissions = 0
        self.completions = 0
        self.failures = 0
        self.cancellations = 0
        self.submission_rate.reset()
        self.completion_rate.reset()
