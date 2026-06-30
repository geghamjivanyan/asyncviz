"""CI-friendly summary lines.

Designed for GitHub Actions ``$GITHUB_STEP_SUMMARY`` + plain stdout
consumption. One line per benchmark with the highlights an engineer
scanning a build log actually wants to see.
"""

from __future__ import annotations

from collections.abc import Iterator

from asyncviz.benchmarks.benchmark_models import BenchmarkSuiteResult
from asyncviz.benchmarks.benchmark_thresholds import (
    label_for,
    summarize_regressions,
)


def emit_ci_summary(suite: BenchmarkSuiteResult) -> Iterator[str]:
    """Yield one summary line at a time. Caller writes them to
    wherever (stdout, $GITHUB_STEP_SUMMARY, log file)."""
    summary = summarize_regressions(suite)
    env = suite.environment
    yield (
        f"asyncviz benchmark suite — python {env.python_version}, "
        f"{env.cpu_count} CPU, "
        f"{suite.duration_wall_ns / 1_000_000:.1f} ms wall"
    )
    yield (
        f"summary: improved={summary.improved} stable={summary.stable} "
        f"regressed={summary.regressed} no_baseline={summary.no_baseline}"
    )
    if summary.worst_regression is not None:
        yield (
            f"worst: {summary.worst_regression.spec_name} "
            f"{summary.worst_regression.delta_ratio:+.1%}"
        )
    for result in suite.results:
        outcome = result.outcome
        stats = outcome.statistics
        verdict = label_for(result.comparison.verdict) if result.comparison is not None else "—"
        if stats is None:
            detail = f" — {outcome.error_detail}" if outcome.error_detail else ""
            yield f"  · {outcome.spec_name}: {outcome.status}{detail} {verdict}"
            continue
        yield (
            f"  · {outcome.spec_name}: "
            f"p50={stats.median_ns / 1000:.1f}µs "
            f"p95={stats.p95_ns / 1000:.1f}µs "
            f"p99={stats.p99_ns / 1000:.1f}µs "
            f"n={stats.sample_count} {verdict}"
        )
