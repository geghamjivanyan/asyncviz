"""Overload detector + threshold tests."""

from __future__ import annotations

from asyncviz.runtime.backpressure import (
    BackpressureConfig,
    OverloadDetector,
    OverloadState,
    PressureSignal,
    state_for_ratio,
)


def test_state_for_ratio_matches_thresholds() -> None:
    cfg = BackpressureConfig()
    assert state_for_ratio(0.0, config=cfg) == OverloadState.NORMAL
    assert state_for_ratio(0.6, config=cfg) == OverloadState.ELEVATED
    assert state_for_ratio(0.85, config=cfg) == OverloadState.OVERLOAD
    assert state_for_ratio(0.99, config=cfg) == OverloadState.EMERGENCY


def test_detector_upgrades_immediately() -> None:
    cfg = BackpressureConfig(
        elevated_threshold=0.3,
        overload_threshold=0.6,
        emergency_threshold=0.9,
        degrade_decay=0.1,
        recovery_hold_ns=0,
    )
    detector = OverloadDetector(cfg)
    # A signal at 0.5 → ELEVATED (after one EMA step at decay=0.1
    # it's essentially the observation).
    snap = detector.observe(
        PressureSignal(source="bus", value=5, capacity=10),
    )
    assert snap.state == OverloadState.ELEVATED


def test_detector_emergency_on_extreme_pressure() -> None:
    cfg = BackpressureConfig(
        elevated_threshold=0.3,
        overload_threshold=0.6,
        emergency_threshold=0.9,
        degrade_decay=0.0001,  # near-zero decay → observation wins
        recovery_hold_ns=0,
    )
    detector = OverloadDetector(cfg)
    snap = detector.observe(
        PressureSignal(source="bus", value=10, capacity=10),
    )
    assert snap.state == OverloadState.EMERGENCY


def test_detector_downgrade_respects_lower_band() -> None:
    cfg = BackpressureConfig(
        elevated_threshold=0.3,
        overload_threshold=0.6,
        emergency_threshold=0.9,
        degrade_decay=0.0001,
        recovery_hold_ns=0,
    )
    detector = OverloadDetector(cfg)
    detector.observe(PressureSignal(source="bus", value=9, capacity=10))
    # Drop way below the elevated threshold → eventually NORMAL.
    for _ in range(5):
        detector.observe(PressureSignal(source="bus", value=0, capacity=10))
    assert detector.state == OverloadState.NORMAL


def test_detector_aggregates_max_signal() -> None:
    cfg = BackpressureConfig(
        elevated_threshold=0.3,
        overload_threshold=0.6,
        emergency_threshold=0.85,
        degrade_decay=0.0001,
        recovery_hold_ns=0,
    )
    detector = OverloadDetector(cfg)
    detector.observe(
        PressureSignal(source="bus", value=1, capacity=10),
    )
    snap = detector.observe(
        PressureSignal(source="websocket", value=9, capacity=10),
    )
    # Max is the websocket signal at 0.9 ≥ emergency_threshold.
    assert snap.state == OverloadState.EMERGENCY


def test_listener_fires_on_transition() -> None:
    cfg = BackpressureConfig(degrade_decay=0.0001, recovery_hold_ns=0)
    detector = OverloadDetector(cfg)
    received = []
    detector.subscribe(lambda prev, nxt: received.append((prev.state, nxt.state)))
    detector.observe(PressureSignal(source="bus", value=9, capacity=10))
    assert any(pair[1] >= OverloadState.OVERLOAD for pair in received)
