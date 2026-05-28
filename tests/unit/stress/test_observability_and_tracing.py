"""Observability + tracing tests."""

from __future__ import annotations

from asyncviz.stress import (
    StressMetrics,
    clear_stress_trace,
    get_stress_metrics,
    get_stress_metrics_snapshot,
    get_stress_trace,
    is_stress_trace_enabled,
    record_stress_trace,
    reset_stress_metrics,
    set_stress_trace_enabled,
)


def test_metrics_start_at_zero() -> None:
    m = StressMetrics()
    snap = m.snapshot()
    assert snap.scenarios_started == 0
    assert snap.operations_completed == 0
    assert snap.survivability_score_mean == 0.0


def test_metrics_record_lifecycle() -> None:
    m = StressMetrics()
    m.record_scenario_started("task")
    m.record_scenario_completed()
    m.record_scenario_verdict("passed")
    m.record_operation_completed(5)
    m.record_operation_failed(2)
    m.record_overload_transition()
    m.record_emergency_action()
    m.record_websocket_disconnect()
    m.record_replay_frame(3)
    m.record_render_frame(4)
    m.record_failure_injection()
    m.record_threshold_violation()
    m.record_survivability_score(0.5)
    snap = m.snapshot()
    assert snap.scenarios_started == 1
    assert snap.operations_completed == 5
    assert snap.operations_failed == 2
    assert snap.overload_transitions == 1
    assert snap.emergency_actions == 1
    assert snap.websocket_disconnects == 1
    assert snap.replay_frames_streamed == 3
    assert snap.render_frames_rendered == 4
    assert snap.failure_injections == 1
    assert snap.threshold_violations == 1
    assert snap.survivability_score_mean == 0.5


def test_metrics_by_category() -> None:
    m = StressMetrics()
    m.record_scenario_started("task")
    m.record_scenario_started("websocket")
    m.record_scenario_started("task")
    snap = m.snapshot()
    assert snap.by_category["task"] == 2
    assert snap.by_category["websocket"] == 1


def test_metrics_reset() -> None:
    m = StressMetrics()
    m.record_scenario_started("task")
    m.record_operation_completed(10)
    m.reset()
    snap = m.snapshot()
    assert snap.scenarios_started == 0
    assert snap.operations_completed == 0


def test_singleton_metrics_resettable() -> None:
    get_stress_metrics().record_operation_completed(5)
    snap1 = get_stress_metrics_snapshot()
    assert snap1.operations_completed >= 5
    reset_stress_metrics()
    assert get_stress_metrics_snapshot().operations_completed == 0


def test_tracing_disabled_by_default() -> None:
    clear_stress_trace()
    set_stress_trace_enabled(False)
    record_stress_trace("signal", "ignored")
    assert get_stress_trace() == ()
    assert is_stress_trace_enabled() is False


def test_tracing_records_when_enabled() -> None:
    set_stress_trace_enabled(True)
    try:
        record_stress_trace("scenario-started", "x")
        record_stress_trace("violation", "y")
        trace = get_stress_trace()
        assert len(trace) == 2
        assert trace[0].kind == "scenario-started"
    finally:
        set_stress_trace_enabled(False)


def test_tracing_clear() -> None:
    set_stress_trace_enabled(True)
    try:
        record_stress_trace("signal", "x")
        clear_stress_trace()
        assert get_stress_trace() == ()
    finally:
        set_stress_trace_enabled(False)


def test_tracing_disable_clears_buffer() -> None:
    set_stress_trace_enabled(True)
    record_stress_trace("signal", "x")
    set_stress_trace_enabled(False)
    assert get_stress_trace() == ()
