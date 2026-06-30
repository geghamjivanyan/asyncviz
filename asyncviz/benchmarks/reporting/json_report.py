"""JSON suite report.

Deterministic structure suitable for CI artifacts, benchmark
dashboards, and human inspection. The schema is versioned so future
tooling can detect old reports + migrate them safely.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from asyncviz.benchmarks.benchmark_models import BenchmarkSuiteResult

REPORT_SCHEMA_VERSION = 1


def suite_to_dict(suite: BenchmarkSuiteResult) -> dict[str, Any]:
    """Convert a suite result into a JSON-safe dict."""
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "environment": asdict(suite.environment),
        "started_at_ns": suite.started_at_ns,
        "ended_at_ns": suite.ended_at_ns,
        "duration_wall_ns": suite.duration_wall_ns,
        "notes": dict(suite.notes),
        "results": [
            {
                "outcome": _outcome_dict(result.outcome),
                "comparison": _comparison_dict(result.comparison),
            }
            for result in suite.results
        ],
        "regression_summary": {
            "regressed": len(suite.regressed),
            "failures": len(suite.failures),
        },
    }


def write_json_report(path: Path, suite: BenchmarkSuiteResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = suite_to_dict(suite)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _outcome_dict(outcome) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    stats = outcome.statistics
    return {
        "spec_name": outcome.spec_name,
        "category": outcome.category,
        "status": outcome.status,
        "error_detail": outcome.error_detail,
        "started_at_ns": outcome.started_at_ns,
        "ended_at_ns": outcome.ended_at_ns,
        "duration_wall_ns": outcome.duration_wall_ns,
        "iterations_run": outcome.iterations_run,
        "warmup_iterations_run": outcome.warmup_iterations_run,
        "statistics": (
            None
            if stats is None
            else {
                "sample_count": stats.sample_count,
                "samples_excluded": stats.samples_excluded,
                "median_ns": stats.median_ns,
                "mean_ns": stats.mean_ns,
                "min_ns": stats.min_ns,
                "max_ns": stats.max_ns,
                "stdev_ns": stats.stdev_ns,
                "p95_ns": stats.p95_ns,
                "p99_ns": stats.p99_ns,
                "coefficient_of_variation": stats.coefficient_of_variation,
                "cumulative_allocations_bytes": stats.cumulative_allocations_bytes,
                "max_allocation_delta_bytes": stats.max_allocation_delta_bytes,
            }
        ),
    }


def _comparison_dict(comparison) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
    if comparison is None:
        return None
    return {
        "spec_name": comparison.spec_name,
        "baseline_p95_ns": comparison.baseline_p95_ns,
        "current_p95_ns": comparison.current_p95_ns,
        "delta_ratio": comparison.delta_ratio,
        "threshold": comparison.threshold,
        "verdict": comparison.verdict,
    }
