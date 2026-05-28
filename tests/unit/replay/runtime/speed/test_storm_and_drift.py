"""Speed-storm + drift simulation tests."""

from __future__ import annotations

from asyncviz.replay.runtime import ReplayClock
from asyncviz.replay.runtime.speed import (
    ReplaySpeedController,
    get_speed_metrics_snapshot,
)


def test_rapid_speed_storm_settles_at_last_value(
    controller: ReplaySpeedController,
) -> None:
    for speed in (2.0, 4.0, 0.5, 8.0, 1.0, 16.0, 0.25, 2.0):
        controller.set_speed(speed)
    assert controller.current_speed == 2.0


def test_repeated_same_speed_storm_collapses(
    controller: ReplaySpeedController,
) -> None:
    for _ in range(20):
        controller.set_speed(4.0)
    snap = get_speed_metrics_snapshot()
    # Only the first request applies; the rest coalesce.
    assert snap.applied == 1
    assert snap.coalesced == 19


def test_drift_sample_under_no_external_interference(
    controller: ReplaySpeedController, clock: ReplayClock,
) -> None:
    controller.set_speed(4.0)
    sample = controller.sample_drift()
    # No external clock poke, so drift should be at or near zero.
    assert abs(sample.drift_ns) < 1_000_000  # < 1 ms


def test_drift_sample_records_metric(
    controller: ReplaySpeedController, clock: ReplayClock,
) -> None:
    before = get_speed_metrics_snapshot()
    controller.sample_drift()
    after = get_speed_metrics_snapshot()
    assert after.drift_samples - before.drift_samples == 1


def test_external_clock_jump_surfaces_as_drift(
    controller: ReplaySpeedController, clock: ReplayClock,
) -> None:
    # External seek-equivalent.
    clock.jump_to(123_456_789)
    sample = controller.sample_drift()
    assert sample.drift_ns != 0


def test_seek_anchor_refresh_clears_drift(
    controller: ReplaySpeedController, clock: ReplayClock,
) -> None:
    clock.jump_to(123_456_789)
    controller.refresh_clock_anchor_from_seek(123_456_789)
    sample = controller.sample_drift()
    # Some real-time elapses between the anchor refresh + the sample
    # call; treat anything under 1 ms of noise as "cleared".
    assert abs(sample.drift_ns) < 1_000_000
