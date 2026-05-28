"""Integrity + diagnostics + tracing tests."""

from __future__ import annotations

from asyncviz.runtime.backpressure import (
    EventBackpressureController,
    OverloadState,
    check_drop_policy,
    check_pressure_ratio,
    check_state_transition,
    clear_backpressure_trace,
    get_backpressure_trace,
    set_backpressure_trace_enabled,
)


def test_check_state_transition_allows_upgrade_skips() -> None:
    # Upgrades may skip tiers.
    assert (
        check_state_transition(OverloadState.NORMAL, OverloadState.EMERGENCY)
        is None
    )


def test_check_state_transition_rejects_downgrade_skips() -> None:
    violation = check_state_transition(
        OverloadState.EMERGENCY, OverloadState.NORMAL,
    )
    assert violation is not None
    assert violation.kind == "downgrade_skip"


def test_check_pressure_ratio_rejects_negative() -> None:
    violation = check_pressure_ratio(-0.1)
    assert violation is not None
    assert violation.kind == "negative_ratio"


def test_check_pressure_ratio_allows_above_one() -> None:
    # Over-capacity is informative, not corrupt.
    assert check_pressure_ratio(1.5) is None


def test_check_drop_policy_rejects_unknown() -> None:
    violation = check_drop_policy("bogus")  # type: ignore[arg-type]
    assert violation is not None
    assert violation.kind == "unknown_drop_policy"


def test_diagnostics_includes_channels(
    controller: EventBackpressureController,
) -> None:
    controller.register_channel("a")
    controller.register_channel("b")
    diag = controller.diagnostics()
    names = {ch.name for ch in diag.channels}
    assert "a" in names
    assert "b" in names


def test_tracing_captures_lifecycle(
    controller: EventBackpressureController,
) -> None:
    set_backpressure_trace_enabled(True)
    try:
        channel = controller.register_channel("trace-bus", capacity=2)
        # Saturate to force a state transition + action dispatch.
        for _ in range(5):
            channel.offer(1)
        controller.tick()
        kinds = {entry.kind for entry in get_backpressure_trace()}
        assert "action-dispatched" in kinds
    finally:
        set_backpressure_trace_enabled(False)
        clear_backpressure_trace()
