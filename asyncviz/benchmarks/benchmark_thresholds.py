"""Regression threshold evaluation helpers.

The runner already produces :class:`BaselineComparison` records;
this module adds suite-level aggregation: how many regressed, the
worst offender, summary verdict strings.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.benchmarks.benchmark_models import (
    BaselineComparison,
    BenchmarkResult,
    BenchmarkSuiteResult,
)


@dataclass(frozen=True, slots=True)
class RegressionSummary:
    """Aggregate regression view of one suite run."""

    total: int
    improved: int
    stable: int
    regressed: int
    no_baseline: int
    worst_regression: BaselineComparison | None
    """The single largest positive delta_ratio across regressed
    benchmarks; ``None`` when there are no regressions."""


def summarize_regressions(suite: BenchmarkSuiteResult) -> RegressionSummary:
    """Compute a regression summary from a suite result."""
    improved = stable = regressed = no_baseline = 0
    worst: BaselineComparison | None = None
    for result in suite.results:
        if result.comparison is None:
            no_baseline += 1
            continue
        v = result.comparison.verdict
        if v == "improved":
            improved += 1
        elif v == "stable":
            stable += 1
        elif v == "regressed":
            regressed += 1
            if worst is None or result.comparison.delta_ratio > worst.delta_ratio:
                worst = result.comparison
        elif v == "no_baseline":
            no_baseline += 1
    return RegressionSummary(
        total=len(suite.results),
        improved=improved,
        stable=stable,
        regressed=regressed,
        no_baseline=no_baseline,
        worst_regression=worst,
    )


def is_regression(result: BenchmarkResult) -> bool:
    return result.comparison is not None and result.comparison.verdict == "regressed"


def label_for(verdict: str) -> str:
    return {
        "improved": "✓ improved",
        "stable": "= stable",
        "regressed": "✗ regressed",
        "no_baseline": "· no baseline",
    }.get(verdict, verdict)
