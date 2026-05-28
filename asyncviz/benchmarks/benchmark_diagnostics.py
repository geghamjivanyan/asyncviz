"""Diagnostics builder for the benchmark layer."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.benchmarks.benchmark_models import BenchmarkSuiteResult
from asyncviz.benchmarks.benchmark_observability import (
    BenchmarkMetricsSnapshot,
    get_benchmark_metrics_snapshot,
)
from asyncviz.benchmarks.benchmark_thresholds import (
    RegressionSummary,
    summarize_regressions,
)
from asyncviz.benchmarks.benchmark_tracing import (
    BenchmarkTraceEntry,
    get_benchmark_trace,
    is_benchmark_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class BenchmarkDiagnostics:
    metrics: BenchmarkMetricsSnapshot
    regression: RegressionSummary | None
    trace_enabled: bool
    recent_trace: tuple[BenchmarkTraceEntry, ...]


def build_benchmark_diagnostics(
    suite: BenchmarkSuiteResult | None = None,
    *,
    trace_limit: int = 32,
) -> BenchmarkDiagnostics:
    trace = get_benchmark_trace()
    if trace_limit > 0:
        trace = trace[-trace_limit:]
    return BenchmarkDiagnostics(
        metrics=get_benchmark_metrics_snapshot(),
        regression=summarize_regressions(suite) if suite is not None else None,
        trace_enabled=is_benchmark_trace_enabled(),
        recent_trace=trace,
    )
