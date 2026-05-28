"""Canonical AsyncViz benchmarking layer.

Public API:

* :func:`benchmark` — decorator for registering benchmarks.
* :class:`BenchmarkRunner` — orchestrates warmup + measurement.
* :class:`BenchmarkConfig` — runner configuration.
* :func:`run_all` — convenience for "run every registered benchmark".

Lower-level pieces live under the submodules (statistics, baselines,
reporting, profiling).
"""

from asyncviz.benchmarks.benchmark_baselines import (
    BaselineFile,
    read_baseline,
    write_baseline,
)
from asyncviz.benchmarks.benchmark_configuration import (
    DEFAULT_MEASURED_ITERATIONS,
    DEFAULT_REGRESSION_THRESHOLD,
    DEFAULT_WARMUP_ITERATIONS,
    BenchmarkConfig,
    OutlierPolicy,
    default_config,
    quick_config,
)
from asyncviz.benchmarks.benchmark_diagnostics import (
    BenchmarkDiagnostics,
    build_benchmark_diagnostics,
)
from asyncviz.benchmarks.benchmark_models import (
    BaselineComparison,
    BenchmarkCategory,
    BenchmarkEnvironment,
    BenchmarkKind,
    BenchmarkOutcome,
    BenchmarkResult,
    BenchmarkSample,
    BenchmarkSpec,
    BenchmarkStatistics,
    BenchmarkSuiteResult,
)
from asyncviz.benchmarks.benchmark_observability import (
    BenchmarkMetricsSnapshot,
    get_benchmark_metrics,
    get_benchmark_metrics_snapshot,
    reset_benchmark_metrics,
)
from asyncviz.benchmarks.benchmark_registry import (
    benchmark,
    get_registry,
    reset_registry,
)
from asyncviz.benchmarks.benchmark_runner import BenchmarkRunner
from asyncviz.benchmarks.benchmark_statistics import (
    aggregate_samples,
    apply_outlier_policy,
)
from asyncviz.benchmarks.benchmark_thresholds import (
    RegressionSummary,
    is_regression,
    label_for,
    summarize_regressions,
)
from asyncviz.benchmarks.benchmark_tracing import (
    BenchmarkTraceEntry,
    BenchmarkTraceKind,
    clear_benchmark_trace,
    get_benchmark_trace,
    is_benchmark_trace_enabled,
    record_benchmark_trace,
    set_benchmark_trace_enabled,
)


def run_all(
    *,
    config: BenchmarkConfig | None = None,
    baselines: dict[str, int] | None = None,
    name_prefix: str | None = None,
    category: BenchmarkCategory | None = None,
) -> BenchmarkSuiteResult:
    """Run every registered benchmark + return the suite result.

    Filtering: ``name_prefix`` keeps only benchmarks whose names
    start with the prefix; ``category`` restricts to a single
    category. Both can be combined.
    """
    runner = BenchmarkRunner(config=config, baselines=baselines)
    specs = get_registry().filtered(
        category=category, name_prefix=name_prefix,
    )
    return runner.run_suite(specs)


__all__ = [
    "DEFAULT_MEASURED_ITERATIONS",
    "DEFAULT_REGRESSION_THRESHOLD",
    "DEFAULT_WARMUP_ITERATIONS",
    "BaselineComparison",
    "BaselineFile",
    "BenchmarkCategory",
    "BenchmarkConfig",
    "BenchmarkDiagnostics",
    "BenchmarkEnvironment",
    "BenchmarkKind",
    "BenchmarkMetricsSnapshot",
    "BenchmarkOutcome",
    "BenchmarkResult",
    "BenchmarkRunner",
    "BenchmarkSample",
    "BenchmarkSpec",
    "BenchmarkStatistics",
    "BenchmarkSuiteResult",
    "BenchmarkTraceEntry",
    "BenchmarkTraceKind",
    "OutlierPolicy",
    "RegressionSummary",
    "aggregate_samples",
    "apply_outlier_policy",
    "benchmark",
    "build_benchmark_diagnostics",
    "clear_benchmark_trace",
    "default_config",
    "get_benchmark_metrics",
    "get_benchmark_metrics_snapshot",
    "get_benchmark_trace",
    "get_registry",
    "is_benchmark_trace_enabled",
    "is_regression",
    "label_for",
    "quick_config",
    "read_baseline",
    "record_benchmark_trace",
    "reset_benchmark_metrics",
    "reset_registry",
    "run_all",
    "set_benchmark_trace_enabled",
    "summarize_regressions",
    "write_baseline",
]
