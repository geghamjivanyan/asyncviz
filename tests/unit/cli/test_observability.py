from __future__ import annotations

from asyncviz.cli.runtime.observability import (
    get_cli_metrics,
    reset_cli_metrics,
)


def setup_function(_fn: object) -> None:
    reset_cli_metrics()


def test_metrics_track_run_lifecycle() -> None:
    metrics = get_cli_metrics()
    metrics.record_run_started()
    metrics.record_subprocess_launch()
    metrics.record_signal_forward()
    metrics.record_run_outcome(ok=True)
    metrics.record_run_durations(total_ms=1234.0, subprocess_ms=1200.0)
    snap = metrics.snapshot()
    assert snap.runs_started == 1
    assert snap.runs_succeeded == 1
    assert snap.subprocess_launches == 1
    assert snap.signal_forwards == 1
    assert snap.last_run_total_ms == 1234.0
    assert snap.last_run_subprocess_ms == 1200.0


def test_metrics_track_failures_and_bootstrap_errors() -> None:
    metrics = get_cli_metrics()
    metrics.record_run_started()
    metrics.record_bootstrap_failure()
    metrics.record_run_outcome(ok=False)
    snap = metrics.snapshot()
    assert snap.runs_failed == 1
    assert snap.bootstrap_failures == 1


def test_metrics_browser_counters() -> None:
    metrics = get_cli_metrics()
    metrics.record_browser_launch(opened=True)
    metrics.record_browser_launch(opened=True)
    metrics.record_browser_launch(opened=False)
    snap = metrics.snapshot()
    assert snap.browser_launches == 2
    assert snap.browser_skips == 1


def test_metrics_parse_duration_average() -> None:
    metrics = get_cli_metrics()
    metrics.record_parse_duration(10.0)
    metrics.record_parse_duration(20.0)
    metrics.record_parse_duration(30.0)
    snap = metrics.snapshot()
    assert snap.average_parse_ms == 20.0


def test_metrics_reset_returns_to_zero() -> None:
    metrics = get_cli_metrics()
    metrics.record_run_started()
    reset_cli_metrics()
    assert get_cli_metrics().snapshot().runs_started == 0
