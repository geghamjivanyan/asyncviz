"""Baseline persistence + threshold tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from asyncviz.benchmarks import (
    BenchmarkRunner,
    benchmark,
    get_registry,
    quick_config,
    read_baseline,
    summarize_regressions,
    write_baseline,
)


def _build_suite() -> tuple[object, BenchmarkRunner]:
    @benchmark(name="t.fast", category="synthetic")
    def fast() -> None:
        return None

    @benchmark(name="t.slow", category="synthetic")
    def slow() -> None:
        # Tiny constant work — keeps the benchmark stable.
        sum(range(50))

    runner = BenchmarkRunner(config=quick_config())
    suite = runner.run_suite(get_registry().all())
    return suite, runner


def test_baseline_round_trip(tmp_path: Path) -> None:
    suite, _ = _build_suite()
    path = tmp_path / "baseline.json"
    write_baseline(path, suite)
    assert path.exists()
    loaded = read_baseline(path)
    assert loaded is not None
    assert "t.fast" in loaded.p95_ns_by_name
    assert "t.slow" in loaded.p95_ns_by_name


def test_read_baseline_returns_none_for_missing(tmp_path: Path) -> None:
    assert read_baseline(tmp_path / "missing.json") is None


def test_read_baseline_rejects_unknown_schema(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version": 99}', encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        read_baseline(path)


def test_regression_summary_categorizes_verdicts(tmp_path: Path) -> None:
    suite, runner = _build_suite()
    baselines = {
        "t.fast": 1_000_000,  # 1ms baseline — current is way faster → improved
        "t.slow": 100,  # 100ns baseline — current is way slower → regressed
    }
    runner.set_baselines(baselines)
    suite = runner.run_suite(get_registry().all())
    summary = summarize_regressions(suite)
    assert summary.improved >= 1
    assert summary.regressed >= 1
    assert summary.worst_regression is not None


def test_no_baseline_when_runner_has_none() -> None:
    suite, _ = _build_suite()
    summary = summarize_regressions(suite)
    assert summary.no_baseline == len(suite.results)
