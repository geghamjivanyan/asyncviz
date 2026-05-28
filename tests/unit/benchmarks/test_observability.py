"""Observability + diagnostics tests."""

from __future__ import annotations

from asyncviz.benchmarks import (
    benchmark,
    build_benchmark_diagnostics,
    clear_benchmark_trace,
    get_benchmark_metrics,
    get_benchmark_metrics_snapshot,
    get_benchmark_trace,
    quick_config,
    run_all,
    set_benchmark_trace_enabled,
)


def test_metrics_get_snapshot_returns_dataclass() -> None:
    snap = get_benchmark_metrics_snapshot()
    assert snap.suites_run == 0
    # Bump a counter, verify it shows up.
    get_benchmark_metrics().record_outcome("ok")
    assert get_benchmark_metrics_snapshot().benchmarks_ok == 1


def test_trace_disabled_by_default() -> None:
    assert get_benchmark_trace() == ()


def test_trace_enabled_captures_entries() -> None:
    from asyncviz.benchmarks import record_benchmark_trace

    set_benchmark_trace_enabled(True)
    try:
        record_benchmark_trace("suite-started", "smoke")
        record_benchmark_trace("benchmark-completed", "t.x")
        kinds = {e.kind for e in get_benchmark_trace()}
        assert "suite-started" in kinds
        assert "benchmark-completed" in kinds
    finally:
        set_benchmark_trace_enabled(False)
        clear_benchmark_trace()


def test_build_diagnostics_includes_suite_summary() -> None:
    @benchmark(name="d.one", category="synthetic")
    def bench() -> None:
        return None

    suite = run_all(config=quick_config())
    diag = build_benchmark_diagnostics(suite)
    assert diag.metrics is not None
    assert diag.regression is not None
    assert diag.regression.total == 1
