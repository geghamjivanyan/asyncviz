"""``python -m asyncviz.benchmarks`` — run the registered suite.

Usage::

    python -m asyncviz.benchmarks
    python -m asyncviz.benchmarks --quick
    python -m asyncviz.benchmarks --category replay
    python -m asyncviz.benchmarks --name-prefix instrumentation.
    python -m asyncviz.benchmarks --json /tmp/bench.json --markdown /tmp/bench.md
    python -m asyncviz.benchmarks --baseline /tmp/baseline.json
    python -m asyncviz.benchmarks --write-baseline /tmp/baseline.json
    python -m asyncviz.benchmarks --track-allocations
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Importing the benchmark categories registers their entries.
import asyncviz.benchmarks.instrumentation
import asyncviz.benchmarks.memory
import asyncviz.benchmarks.replay
import asyncviz.benchmarks.stress
import asyncviz.benchmarks.websocket  # noqa: F401
from asyncviz.benchmarks import (
    BenchmarkConfig,
    default_config,
    quick_config,
    read_baseline,
    run_all,
    set_benchmark_trace_enabled,
    summarize_regressions,
    write_baseline,
)
from asyncviz.benchmarks.reporting import (
    emit_ci_summary,
    write_json_report,
    write_markdown_report,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="asyncviz.benchmarks",
        description="Run AsyncViz benchmarks + emit reports.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use the quick benchmark config",
    )
    parser.add_argument("--category", default=None, help="Filter by category")
    parser.add_argument(
        "--name-prefix",
        default=None,
        help="Filter by name prefix",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Compare against this baseline file",
    )
    parser.add_argument(
        "--write-baseline",
        type=Path,
        default=None,
        help="Write a new baseline after the run",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Write full JSON report to this path",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help="Write markdown summary to this path",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Enable benchmark tracing during the run",
    )
    parser.add_argument(
        "--track-allocations",
        action="store_true",
        help="Capture per-sample tracemalloc deltas (slow)",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit nonzero if any regression is detected vs baseline",
    )
    return parser.parse_args(argv)


def _resolve_config(args: argparse.Namespace) -> BenchmarkConfig:
    base = quick_config() if args.quick else default_config()
    return BenchmarkConfig(
        warmup_iterations=base.warmup_iterations,
        measured_iterations=base.measured_iterations,
        min_samples=base.min_samples,
        outlier_policy=base.outlier_policy,
        mad_threshold=base.mad_threshold,
        iqr_factor=base.iqr_factor,
        regression_threshold=base.regression_threshold,
        report_percentiles=base.report_percentiles,
        disable_gc_during_run=base.disable_gc_during_run,
        isolate_per_benchmark=base.isolate_per_benchmark,
        track_allocations=args.track_allocations,
        deterministic_seed=base.deterministic_seed,
        fail_on_regression=args.fail_on_regression,
        extras=dict(base.extras),
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.trace:
        set_benchmark_trace_enabled(True)

    config = _resolve_config(args)
    baselines = None
    if args.baseline is not None:
        bf = read_baseline(args.baseline)
        if bf is not None:
            baselines = bf.p95_ns_by_name

    suite = run_all(
        config=config,
        baselines=baselines,
        name_prefix=args.name_prefix,
        category=args.category,  # type: ignore[arg-type]
    )

    for line in emit_ci_summary(suite):
        print(line)

    if args.json is not None:
        write_json_report(args.json, suite)
        print(f"json report → {args.json}")
    if args.markdown is not None:
        write_markdown_report(args.markdown, suite)
        print(f"markdown report → {args.markdown}")
    if args.write_baseline is not None:
        write_baseline(args.write_baseline, suite)
        print(f"baseline → {args.write_baseline}")

    summary = summarize_regressions(suite)
    if args.fail_on_regression and summary.regressed > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
