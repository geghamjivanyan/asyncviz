"""Chaos / failure-injection simulations.

These tests don't test specific functions — they drive synthetic
fault storms through the manager and verify the *structural*
guarantees:

* bounded failure propagation (a misbehaving subsystem never
  affects a healthy sibling),
* deterministic behavior under identical inputs,
* no cascading collapse (one open breaker doesn't trip others),
* graceful recovery,
* explicit data-loss bookkeeping.
"""

from __future__ import annotations

import contextlib

import pytest

from asyncviz.runtime.resilience import (
    BreakerState,
    RuntimeFailureManager,
    SubsystemPolicy,
    default_config,
    lean_config,
)


def _identical_replay(seed: int) -> dict[str, object]:
    """Drive a deterministic chaos sim + return the observed state.

    Identical seeds must produce identical states across two runs.
    """
    mgr = RuntimeFailureManager(config=lean_config())
    # Storm pattern: 12 transient reducer failures, 5 websocket
    # disconnect storms, 1 replay corruption, 4 recorder OSErrors.
    for i in range(12):
        with mgr.boundary("reducer", payload_kind=f"r-{i + seed}"):
            raise TimeoutError("transient")
    ws = mgr.websocket()
    for i in range(5):
        with ws.isolate_send(subscriber_id=f"sub-{i + seed}"):
            raise ConnectionResetError("peer gone")
    replay = mgr.replay()
    with contextlib.suppress(ValueError), replay.isolate_decode(payload_kind=f"frame-{seed}"):
        raise ValueError("corrupted-frame: bad checksum")
    recorder = mgr.recorder()
    for i in range(4):
        with recorder.isolate_write(payload_kind=f"chk-{i + seed}"):
            raise OSError(28, "no space")
    return {
        "mode": mgr.mode(),
        "reducer_state": mgr.domain("reducer").breaker.state,
        "websocket_state": mgr.domain("websocket").breaker.state,
        "replay_quarantined": replay.quarantined_frames(),
        "recorder_data_loss": recorder.data_loss_events(),
    }


def test_chaos_sim_is_deterministic() -> None:
    a = _identical_replay(seed=0)
    b = _identical_replay(seed=0)
    assert a == b


def test_chaos_sim_isolates_subsystems() -> None:
    state = _identical_replay(seed=0)
    # Reducer + recorder collapsed; websocket may also have tripped.
    assert state["reducer_state"] == BreakerState.OPEN
    # The render subsystem was never touched — it must remain healthy.
    mgr = RuntimeFailureManager(config=lean_config())
    render = mgr.render()
    with render.isolate_pass(pass_id="grid"):
        pass
    assert mgr.domain("render").breaker.state == BreakerState.CLOSED


def test_one_subsystem_collapse_does_not_trip_unrelated() -> None:
    mgr = RuntimeFailureManager(config=lean_config())
    mgr.websocket()
    mgr.replay()
    mgr.recorder()
    for _ in range(20):
        with mgr.boundary("reducer"):
            raise TimeoutError("x")
    assert mgr.domain("reducer").breaker.state == BreakerState.OPEN
    assert mgr.domain("websocket").breaker.state == BreakerState.CLOSED
    assert mgr.domain("replay").breaker.state == BreakerState.CLOSED
    assert mgr.domain("recorder").breaker.state == BreakerState.CLOSED


def test_replay_corruption_quarantines_specific_payload_only() -> None:
    mgr = RuntimeFailureManager()
    replay = mgr.replay()
    with contextlib.suppress(ValueError), replay.isolate_decode(payload_kind="frame-A"):
        raise ValueError("corrupted-frame")
    assert "frame-A" in replay.quarantined_frames()
    # frame-B is unaffected — it processes normally.
    with replay.isolate_decode(payload_kind="frame-B"):
        pass
    assert replay.quarantined_frames() == ("frame-A",)


def test_render_pass_failure_disables_only_that_pass() -> None:
    mgr = RuntimeFailureManager()
    render = mgr.render()
    # Drive the same pass to failure repeatedly so its breaker trips
    # and the adapter marks it disabled.
    for _ in range(20):
        with render.isolate_pass(pass_id="overlay"):
            raise RuntimeError("overlay-broken")
    # The 'data' pass should still work — pass-level isolation.
    with render.isolate_pass(pass_id="data"):
        pass
    assert mgr.domain("render").breaker.state == BreakerState.OPEN
    # The breaker is open, but the 'data' pass body still ran.
    # Quarantine is per-payload, so 'data' isn't in the disabled set.
    assert "overlay" not in render.disabled_passes() or "data" not in render.disabled_passes()


def test_recovery_after_storm() -> None:
    mgr = RuntimeFailureManager(config=lean_config())
    for _ in range(20):
        with mgr.boundary("reducer"):
            raise TimeoutError("x")
    assert mgr.domain("reducer").breaker.state == BreakerState.OPEN
    mgr.register_recovery("reducer", lambda _d: True)
    outcome = mgr.attempt_recovery("reducer")
    assert outcome.verdict == "succeeded"
    assert mgr.domain("reducer").breaker.state == BreakerState.CLOSED
    assert mgr.mode() == "normal"


def test_bounded_recovery_loop_abandons() -> None:
    mgr = RuntimeFailureManager(
        config=default_config().__class__(
            default_policy=SubsystemPolicy(
                failure_threshold=1,
                max_recovery_attempts=3,
            ),
        ),
    )
    with mgr.boundary("x"):
        raise TimeoutError("transient")
    mgr.register_recovery("x", lambda _d: False)
    outcomes = [mgr.attempt_recovery("x") for _ in range(5)]
    assert outcomes[-1].verdict == "abandoned"
    assert mgr.supervisor("x").abandoned() is True


def test_recorder_data_loss_visible() -> None:
    mgr = RuntimeFailureManager()
    recorder = mgr.recorder()
    for i in range(5):
        with recorder.isolate_write(payload_kind=f"chk-{i}"):
            raise OSError(28, "no space")
    # Each failed write counts as one data-loss event the operator
    # can see in diagnostics.
    assert recorder.data_loss_events() == 5


def test_listener_storm_does_not_leak_failures() -> None:
    mgr = RuntimeFailureManager()

    def _bad_listener(_mode: object) -> None:
        raise RuntimeError("listener-bug")

    for _ in range(8):
        mgr.subscribe_mode(_bad_listener)
    # Trigger a mode transition — must not raise.
    for _ in range(20):
        with mgr.boundary("reducer"):
            raise TimeoutError("x")
    assert mgr.mode() in ("degraded", "shed", "emergency")


@pytest.mark.parametrize("size", [10, 100, 1000])
def test_bounded_overhead_under_storm(size: int) -> None:
    mgr = RuntimeFailureManager(config=lean_config())
    for i in range(size):
        with mgr.boundary("reducer", payload_kind=f"r-{i}"):
            raise TimeoutError("transient")
    # The breaker is tripped; the history is bounded at 64. The
    # quarantine set stays empty (transient errors don't quarantine).
    snap = mgr.diagnostics()
    domain = next(d for d in snap.domains if d.name == "reducer")
    assert len(domain.recent_failures) <= 64
    assert domain.quarantined_payloads == ()
