"""End-to-end ReplaySpeedController tests."""

from __future__ import annotations

import math

import pytest

from asyncviz.replay.runtime import ReplayClock
from asyncviz.replay.runtime.speed import (
    ReplaySpeedConfig,
    ReplaySpeedController,
    SpeedPhase,
    get_speed_metrics_snapshot,
)


def test_initial_state(controller: ReplaySpeedController) -> None:
    assert controller.current_speed == 1.0
    assert controller.phase.phase == SpeedPhase.IDLE


def test_set_speed_applies_to_clock(
    controller: ReplaySpeedController, clock: ReplayClock,
) -> None:
    result = controller.set_speed(2.0)
    assert result.applied_speed == 2.0
    assert clock.speed == 2.0
    assert controller.phase.phase == SpeedPhase.APPLIED


def test_coalesces_repeated_same_speed(
    controller: ReplaySpeedController,
) -> None:
    first = controller.set_speed(2.0)
    second = controller.set_speed(2.0)
    assert not first.coalesced
    assert second.coalesced
    assert controller.current_speed == 2.0


def test_clamps_out_of_range(
    controller: ReplaySpeedController,
) -> None:
    result = controller.set_speed(99.0)
    assert result.clamped
    assert result.applied_speed == controller.config.max_speed


def test_rejects_zero_and_negative(
    controller: ReplaySpeedController,
) -> None:
    result = controller.set_speed(0)
    assert result.rejected
    result = controller.set_speed(-1)
    assert result.rejected


def test_rejects_non_finite(controller: ReplaySpeedController) -> None:
    result = controller.set_speed(math.inf)
    assert result.rejected


def test_increase_and_decrease_speed(
    controller: ReplaySpeedController,
) -> None:
    controller.set_speed(1.0)
    controller.increase_speed()
    assert controller.current_speed == 2.0
    controller.increase_speed()
    assert controller.current_speed == 4.0
    controller.decrease_speed()
    assert controller.current_speed == 2.0


def test_restore_default(controller: ReplaySpeedController) -> None:
    controller.set_speed(8.0)
    controller.restore_default()
    assert controller.current_speed == 1.0


def test_snap_to_nearest_preset(controller: ReplaySpeedController) -> None:
    # Place the clock at a non-preset value by setting it directly,
    # then snap.
    controller.set_speed(2.5)
    controller.snap_to_nearest_preset()
    assert controller.current_speed in {2.0, 4.0}


def test_history_records_transitions(
    controller: ReplaySpeedController,
) -> None:
    controller.set_speed(2.0)
    controller.set_speed(4.0)
    history = controller.history
    assert len(history) == 2
    assert history[-1].new_speed == 4.0


def test_listener_fires_on_change(
    controller: ReplaySpeedController,
) -> None:
    received: list = []
    controller.subscribe_change(lambda result: received.append(result))
    controller.set_speed(2.0)
    controller.set_speed(2.0)  # coalesces but still calls listener
    assert len(received) == 2
    assert received[0].applied_speed == 2.0
    assert received[1].coalesced


def test_phase_listener_fires(
    controller: ReplaySpeedController,
) -> None:
    transitions: list = []
    controller.subscribe_phase(
        lambda prev, nxt: transitions.append((prev.phase, nxt.phase)),
    )
    controller.set_speed(2.0)
    # idle → applying → applied
    kinds = [pair[1] for pair in transitions]
    assert SpeedPhase.APPLYING in kinds
    assert SpeedPhase.APPLIED in kinds


def test_metrics_track_lifecycle(
    controller: ReplaySpeedController,
) -> None:
    before = get_speed_metrics_snapshot()
    controller.set_speed(2.0)
    controller.set_speed(2.0)  # coalesce
    controller.set_speed(99.0)  # clamp
    controller.set_speed(0)  # reject
    after = get_speed_metrics_snapshot()
    assert after.requested - before.requested == 4
    assert after.applied - before.applied >= 2
    assert after.coalesced - before.coalesced == 1
    assert after.clamped - before.clamped == 1
    assert after.rejected - before.rejected == 1


def test_rejected_config_invariants() -> None:
    with pytest.raises(ValueError):
        ReplaySpeedConfig(default_speed=999)
    with pytest.raises(ValueError):
        ReplaySpeedConfig(min_speed=0)
    with pytest.raises(ValueError):
        ReplaySpeedConfig(min_speed=10, max_speed=1)
