"""RuntimeFailureManager façade tests."""

from __future__ import annotations

import contextlib

import pytest

from asyncviz.runtime.resilience import (
    BreakerState,
    RuntimeFailureManager,
    SubsystemPolicy,
    SubsystemUnavailable,
    default_config,
    lean_config,
    relaxed_config,
)


def test_register_is_idempotent() -> None:
    mgr = RuntimeFailureManager()
    a = mgr.register("x")
    b = mgr.register("x")
    assert a is b


def test_default_lean_relaxed_configs_distinct() -> None:
    default_threshold = default_config().default_policy.failure_threshold
    assert default_threshold > lean_config().default_policy.failure_threshold
    assert relaxed_config().default_policy.failure_threshold > default_threshold


def test_per_subsystem_policy_used_at_registration() -> None:
    mgr = RuntimeFailureManager(config=default_config())
    domain = mgr.register("recorder")
    assert domain.policy.quarantine_payload_kind is True


def test_custom_policy_override() -> None:
    mgr = RuntimeFailureManager()
    mgr.register("custom-x", policy=SubsystemPolicy(failure_threshold=99))
    assert mgr.domain("custom-x").policy.failure_threshold == 99


def test_boundary_records_failure_in_metrics() -> None:
    mgr = RuntimeFailureManager()
    with mgr.boundary("x"):
        raise TimeoutError("transient")
    snap = mgr.metrics.snapshot() if False else mgr.diagnostics().metrics
    assert snap.failures_observed == 1
    assert snap.by_subsystem["x"] == 1


def test_breaker_trip_changes_mode_to_degraded() -> None:
    mgr = RuntimeFailureManager(
        config=default_config().__class__(
            default_policy=SubsystemPolicy(failure_threshold=2, failure_window_s=10),
        ),
    )
    for _ in range(2):
        with mgr.boundary("x"):
            raise TimeoutError("transient")
    assert mgr.domain("x").breaker.state == BreakerState.OPEN
    assert mgr.mode() == "degraded"


def test_critical_collapse_triggers_emergency() -> None:
    mgr = RuntimeFailureManager()
    recorder = mgr.recorder()
    for i in range(6):
        with recorder.isolate_write(payload_kind=f"chk-{i}"):
            raise OSError(28, "no space")
    assert mgr.mode() == "emergency"


def test_halt_on_critical_flag() -> None:
    cfg = default_config().__class__(halt_on_critical_subsystem=True)
    mgr = RuntimeFailureManager(config=cfg)
    recorder = mgr.recorder()
    for i in range(6):
        with recorder.isolate_write(payload_kind=f"chk-{i}"):
            raise OSError(28, "no space")
    assert mgr.mode() == "halt"


def test_replay_corruption_propagates_and_quarantines() -> None:
    mgr = RuntimeFailureManager()
    replay = mgr.replay()
    with contextlib.suppress(ValueError), replay.isolate_decode(payload_kind="frame-42"):
        raise ValueError("corrupted-frame")
    assert replay.quarantined_frames() == ("frame-42",)


def test_websocket_send_isolates_per_subscriber() -> None:
    mgr = RuntimeFailureManager()
    ws = mgr.websocket()
    for _ in range(20):
        with ws.isolate_send(subscriber_id="bad-sub"):
            raise ConnectionResetError("peer gone")
    assert mgr.domain("websocket").breaker.state == BreakerState.OPEN
    assert "bad-sub" in ws.disconnected_subscribers()


def test_subscribe_mode_listener() -> None:
    mgr = RuntimeFailureManager()
    received = []
    mgr.subscribe_mode(received.append)
    for _ in range(10):
        with mgr.boundary("reducer"):
            raise TimeoutError("x")
    assert "degraded" in received


def test_unsubscribe_mode_listener() -> None:
    mgr = RuntimeFailureManager()
    received = []
    unsub = mgr.subscribe_mode(received.append)
    unsub()
    for _ in range(10):
        with mgr.boundary("reducer"):
            raise TimeoutError("x")
    assert received == []


def test_report_exception_explicit() -> None:
    mgr = RuntimeFailureManager()
    mgr.report_exception("x", ValueError("corrupted-frame"), payload_kind="p")
    snap = mgr.diagnostics()
    assert snap.metrics.failures_observed == 1


def test_report_marker_explicit() -> None:
    mgr = RuntimeFailureManager()
    mgr.report_marker("x", "disk-full")
    snap = mgr.diagnostics()
    assert snap.metrics.failures_observed == 1
    assert snap.metrics.by_failure_kind["resource"] == 1


def test_force_mode_overrides_observed_state() -> None:
    mgr = RuntimeFailureManager()
    mgr.force_mode("halt")
    assert mgr.mode() == "halt"


def test_register_recovery_and_attempt() -> None:
    mgr = RuntimeFailureManager()
    for _ in range(10):
        with mgr.boundary("reducer"):
            raise TimeoutError("x")
    called = []

    def _hook(_domain):
        called.append("yes")
        return True

    mgr.register_recovery("reducer", _hook)
    outcome = mgr.attempt_recovery("reducer")
    assert outcome.verdict == "succeeded"
    assert called == ["yes"]
    assert mgr.domain("reducer").breaker.state == BreakerState.CLOSED


async def test_register_async_recovery() -> None:
    mgr = RuntimeFailureManager()
    for _ in range(10):
        with mgr.boundary("reducer"):
            raise TimeoutError("x")

    async def _hook(_domain):
        return True

    mgr.register_async_recovery("reducer", _hook)
    outcome = await mgr.attempt_recovery_async("reducer")
    assert outcome.verdict == "succeeded"


def test_diagnostics_includes_subsystems_and_supervisors() -> None:
    mgr = RuntimeFailureManager()
    mgr.register("a")
    mgr.register("b")
    diag = mgr.diagnostics()
    names = {d.name for d in diag.domains}
    assert names == {"a", "b"}
    assert len(diag.supervisors) == 2


def test_reset_clears_state() -> None:
    mgr = RuntimeFailureManager()
    with mgr.boundary("x"):
        raise TimeoutError("x")
    mgr.reset()
    diag = mgr.diagnostics()
    assert all(d.total_failures == 0 for d in diag.domains)
    assert mgr.mode() == "normal"


def test_unknown_subsystem_uses_default_policy() -> None:
    mgr = RuntimeFailureManager()
    mgr.register("custom-foo")
    assert (
        mgr.domain("custom-foo").policy.failure_threshold
        == default_config().default_policy.failure_threshold
    )


def test_session_boundary_raises_when_open() -> None:
    mgr = RuntimeFailureManager()
    for _ in range(10):
        with mgr.boundary("x"):
            raise TimeoutError("x")
    with pytest.raises(SubsystemUnavailable), mgr.boundary("x", swallow_unavailable=False):
        pass
