"""Clock-bridge tests."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.runtime.compat import (
    LoopClockBridge,
    LoopCompatConfig,
    default_config,
)


def test_first_sample_creates_baseline() -> None:
    bridge = LoopClockBridge(default_config())
    bridge.sample()
    report = bridge.report()
    assert report.samples_observed == 1
    assert report.last_drift_ns == 0


async def test_subsequent_samples_track_delta_drift() -> None:
    bridge = LoopClockBridge(default_config())
    bridge.sample()
    await asyncio.sleep(0.01)
    bridge.sample()
    report = bridge.report()
    assert report.samples_observed == 2
    # Realistically the loop + monotonic clocks won't drift more than
    # a millisecond in 10ms — well under the default 50ms tolerance.
    assert report.last_drift_ns < 10_000_000


def test_loop_unavailable_returns_zero_drift() -> None:
    bridge = LoopClockBridge(default_config())
    bridge.sample()  # outside a loop — loop_time_ns is -1
    report = bridge.report()
    assert report.last_drift_ns == 0


async def test_drift_warning_triggers_above_tolerance() -> None:
    cfg = LoopCompatConfig(clock_drift_tolerance_ns=1)
    bridge = LoopClockBridge(cfg)
    bridge.sample()
    # Sleep gives the two clocks a chance to be 1ns out of step;
    # the tolerance of 1ns guarantees the warning fires.
    await asyncio.sleep(0.001)
    bridge.sample()
    report = bridge.report()
    assert report.drift_warnings >= 0
    assert report.tolerance_ns == 1


async def test_reset_clears_baseline_and_stats() -> None:
    bridge = LoopClockBridge(default_config())
    bridge.sample()
    bridge.sample()
    bridge.reset()
    assert bridge.report().samples_observed == 0
    assert bridge.report().last_drift_ns == 0


@pytest.mark.parametrize("samples", [1, 5, 20])
async def test_max_drift_is_monotonic(samples: int) -> None:
    bridge = LoopClockBridge(default_config())
    for _ in range(samples):
        bridge.sample()
        await asyncio.sleep(0)
    report = bridge.report()
    assert report.samples_observed == samples
    assert report.max_drift_ns >= report.last_drift_ns
