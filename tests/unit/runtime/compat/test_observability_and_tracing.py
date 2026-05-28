"""Observability + tracing tests."""

from __future__ import annotations

from asyncviz.runtime.compat import (
    LoopCompatMetrics,
    clear_loop_compat_trace,
    get_loop_compat_metrics,
    get_loop_compat_metrics_snapshot,
    get_loop_compat_trace,
    is_loop_compat_trace_enabled,
    loop_compat_trace_capacity,
    record_loop_compat_trace,
    reset_loop_compat_metrics,
    set_loop_compat_trace_enabled,
)


def test_metrics_start_at_zero() -> None:
    m = LoopCompatMetrics()
    snap = m.snapshot()
    assert snap.managers_attached == 0
    assert snap.uvloop_installs_attempted == 0


def test_metrics_record_lifecycle() -> None:
    m = LoopCompatMetrics()
    m.record_manager_attached("asyncio")
    m.record_uvloop_install_attempt()
    m.record_uvloop_install_success()
    m.record_uvloop_install_failure()
    m.record_fallback_activation(3)
    m.record_drift_warning(2)
    m.record_integrity_violation()
    m.record_replay_drift_frame()
    m.record_websocket_cadence_deviation()
    m.record_scheduler_past_due()
    snap = m.snapshot()
    assert snap.managers_attached == 1
    assert snap.uvloop_installs_attempted == 1
    assert snap.uvloop_installs_succeeded == 1
    assert snap.uvloop_installs_failed == 1
    assert snap.fallback_activations == 3
    assert snap.drift_warnings == 2
    assert snap.by_loop_kind["asyncio"] == 1


def test_singleton_reset() -> None:
    get_loop_compat_metrics().record_manager_attached("uvloop")
    assert get_loop_compat_metrics_snapshot().managers_attached >= 1
    reset_loop_compat_metrics()
    assert get_loop_compat_metrics_snapshot().managers_attached == 0


def test_tracing_disabled_by_default() -> None:
    clear_loop_compat_trace()
    set_loop_compat_trace_enabled(False)
    record_loop_compat_trace("manager-attached", "ignored")
    assert get_loop_compat_trace() == ()
    assert is_loop_compat_trace_enabled() is False


def test_tracing_records_when_enabled() -> None:
    set_loop_compat_trace_enabled(True)
    try:
        record_loop_compat_trace("manager-attached", "x")
        trace = get_loop_compat_trace()
        assert len(trace) == 1
        assert trace[0].kind == "manager-attached"
    finally:
        set_loop_compat_trace_enabled(False)


def test_tracing_capacity_is_resizable() -> None:
    set_loop_compat_trace_enabled(True, capacity=8)
    try:
        for i in range(16):
            record_loop_compat_trace("diagnostic", f"i={i}")
        assert len(get_loop_compat_trace()) == 8
        assert loop_compat_trace_capacity() == 8
    finally:
        set_loop_compat_trace_enabled(False, capacity=256)


def test_disabling_tracing_clears_buffer() -> None:
    set_loop_compat_trace_enabled(True)
    record_loop_compat_trace("manager-attached", "x")
    set_loop_compat_trace_enabled(False)
    assert get_loop_compat_trace() == ()
