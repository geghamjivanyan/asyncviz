"""Budget + adaptive controller tests."""

from __future__ import annotations

from asyncviz.runtime.sampling import (
    AdaptiveSamplingController,
    EventSampler,
    SamplingBudget,
    default_config,
)


def test_budget_records_retained() -> None:
    budget = SamplingBudget(target_events=5, window_ns=10_000_000_000)
    for _ in range(3):
        budget.record_retained()
    snap = budget.snapshot()
    assert snap.current_retained == 3
    assert not snap.over_budget


def test_budget_trips_over_target() -> None:
    budget = SamplingBudget(target_events=2, window_ns=10_000_000_000)
    for _ in range(5):
        budget.record_retained()
    assert budget.over_budget


def test_budget_rolls_over_after_window() -> None:
    # Use a very short window to exercise the rollover path.
    budget = SamplingBudget(target_events=2, window_ns=1_000_000)  # 1ms
    budget.record_retained()
    budget.record_retained()
    # Sleep just long enough for the window to roll.
    import time

    time.sleep(0.005)
    snap = budget.snapshot()
    assert snap.current_retained == 0


def test_adaptive_controller_engages_overload() -> None:
    sampler = EventSampler(default_config())
    controller = AdaptiveSamplingController(sampler=sampler)
    # Below the high-water mark — no engagement.
    snap = controller.observe_pressure(1000)
    assert not snap.overload
    # Spike above the high-water mark; due to EMA smoothing it may
    # take a few samples.
    for _ in range(50):
        snap = controller.observe_pressure(10_000_000)
    assert snap.overload


def test_adaptive_controller_releases_overload() -> None:
    sampler = EventSampler(default_config())
    controller = AdaptiveSamplingController(sampler=sampler)
    for _ in range(50):
        controller.observe_pressure(10_000_000)
    assert sampler.overload
    # Reset back to low pressure.
    for _ in range(200):
        controller.observe_pressure(0)
    assert not sampler.overload


def test_pressure_source_callable() -> None:
    sampler = EventSampler(default_config())
    pressure = [0]
    controller = AdaptiveSamplingController(
        sampler=sampler,
        pressure_source=lambda: pressure[0],
    )
    pressure[0] = 5_000_000
    for _ in range(20):
        controller.tick()
    # Smoothed pressure should have caught up.
    assert controller.snapshot().smoothed_pressure > 0
