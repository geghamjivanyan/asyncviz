"""Observability + tracing tests."""

from __future__ import annotations

from asyncviz.runtime.resilience import (
    IsolationMetrics,
    clear_isolation_trace,
    get_isolation_metrics,
    get_isolation_metrics_snapshot,
    get_isolation_trace,
    is_isolation_trace_enabled,
    record_isolation_trace,
    reset_isolation_metrics,
    set_isolation_trace_enabled,
)


def test_metrics_start_at_zero() -> None:
    m = IsolationMetrics()
    snap = m.snapshot()
    assert snap.subsystems_registered == 0
    assert snap.failures_observed == 0
    assert snap.last_mode == "normal"


def test_metrics_record_lifecycle() -> None:
    m = IsolationMetrics()
    m.record_subsystem_registered()
    m.record_failure("replay", "corruption")
    m.record_breaker_trip()
    m.record_breaker_close()
    m.record_recovery_attempt("succeeded")
    m.record_recovery_attempt("failed")
    m.record_recovery_attempt("abandoned")
    m.record_payload_quarantine()
    m.record_boundary_admission()
    m.record_boundary_rejection()
    m.record_mode_transition("emergency")
    snap = m.snapshot()
    assert snap.subsystems_registered == 1
    assert snap.failures_observed == 1
    assert snap.by_subsystem["replay"] == 1
    assert snap.by_failure_kind["corruption"] == 1
    assert snap.breaker_trips == 1
    assert snap.breaker_closes == 1
    assert snap.recovery_attempts == 3
    assert snap.recovery_successes == 1
    assert snap.recovery_failures == 1
    assert snap.recovery_abandonments == 1
    assert snap.last_mode == "emergency"


def test_metrics_reset() -> None:
    m = IsolationMetrics()
    m.record_failure("x", "transient")
    m.reset()
    assert m.snapshot().failures_observed == 0


def test_singleton_reset() -> None:
    get_isolation_metrics().record_failure("x", "transient")
    assert get_isolation_metrics_snapshot().failures_observed >= 1
    reset_isolation_metrics()
    assert get_isolation_metrics_snapshot().failures_observed == 0


def test_tracing_disabled_by_default() -> None:
    clear_isolation_trace()
    set_isolation_trace_enabled(False)
    record_isolation_trace("failure-observed", "ignored")
    assert get_isolation_trace() == ()
    assert is_isolation_trace_enabled() is False


def test_tracing_when_enabled() -> None:
    set_isolation_trace_enabled(True)
    try:
        record_isolation_trace("breaker-trip", "replay")
        trace = get_isolation_trace()
        assert len(trace) == 1
        assert trace[0].kind == "breaker-trip"
    finally:
        set_isolation_trace_enabled(False)


def test_disabling_tracing_clears_buffer() -> None:
    set_isolation_trace_enabled(True)
    record_isolation_trace("breaker-trip", "x")
    set_isolation_trace_enabled(False)
    assert get_isolation_trace() == ()
