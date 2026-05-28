"""Observability + tracing tests."""

from __future__ import annotations

from tests.integration._framework import (
    IntegrationMetrics,
    clear_integration_trace,
    get_integration_metrics,
    get_integration_metrics_snapshot,
    get_integration_trace,
    is_integration_trace_enabled,
    record_integration_trace,
    reset_integration_metrics,
    set_integration_trace_enabled,
)


def test_metrics_lifecycle() -> None:
    m = IntegrationMetrics()
    m.record_scenario_started("runtime")
    m.record_verdict("passed")
    m.record_scenario_completed()
    m.record_determinism_run(diverged=False)
    m.record_uvloop_run(diverged=True)
    m.record_operations(completed=10, failed=2)
    m.record_threshold_violations(1)
    snap = m.snapshot()
    assert snap.scenarios_started == 1
    assert snap.scenarios_passed == 1
    assert snap.determinism_runs == 1
    assert snap.uvloop_divergences == 1
    assert snap.operations_completed == 10


def test_singleton_reset() -> None:
    get_integration_metrics().record_scenario_started("runtime")
    assert get_integration_metrics_snapshot().scenarios_started >= 1
    reset_integration_metrics()
    assert get_integration_metrics_snapshot().scenarios_started == 0


def test_tracing_off_by_default() -> None:
    set_integration_trace_enabled(False)
    clear_integration_trace()
    record_integration_trace("scenario-started", "ignored")
    assert get_integration_trace() == ()
    assert is_integration_trace_enabled() is False


def test_tracing_records_when_on() -> None:
    set_integration_trace_enabled(True)
    try:
        record_integration_trace("violation", "x")
        trace = get_integration_trace()
        assert len(trace) == 1
        assert trace[0].kind == "violation"
    finally:
        set_integration_trace_enabled(False)
