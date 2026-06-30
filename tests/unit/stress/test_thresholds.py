"""Threshold-evaluator tests."""

from __future__ import annotations

import pytest

from asyncviz.stress import (
    ScalabilityThresholds,
    compute_survivability_score,
    evaluate_violations,
    verdict_for,
)


def test_no_violations_when_under_limits() -> None:
    violations = evaluate_violations(
        thresholds=ScalabilityThresholds(),
        dropped_frames=0,
        replay_drift_ms=0,
        websocket_backlog=0,
        memory_growth_bytes=0,
        fps=120.0,
        emergency_transitions=0,
        survivability_score=1.0,
    )
    assert violations == ()


def test_dropped_frames_violation() -> None:
    violations = evaluate_violations(
        thresholds=ScalabilityThresholds(max_dropped_frames=10),
        dropped_frames=100,
    )
    assert any(v.metric == "dropped_frames" for v in violations)


def test_fps_violation() -> None:
    violations = evaluate_violations(
        thresholds=ScalabilityThresholds(min_fps=60.0),
        fps=12.0,
    )
    assert any(v.metric == "fps" for v in violations)


def test_survivability_violation() -> None:
    violations = evaluate_violations(
        thresholds=ScalabilityThresholds(min_survivability_score=0.95),
        survivability_score=0.1,
    )
    assert any(v.metric == "survivability_score" for v in violations)


def test_violation_can_be_disabled_with_none() -> None:
    violations = evaluate_violations(
        thresholds=ScalabilityThresholds(
            max_dropped_frames=None,
            min_fps=None,
        ),
        dropped_frames=10_000,
        fps=0.0,
    )
    assert violations == ()


@pytest.mark.parametrize(
    "errored,violations,warn_only,expected",
    [
        (True, (), False, "errored"),
        (False, (), False, "passed"),
        (False, ("v",), False, "failed"),
        (False, ("v",), True, "warned"),
    ],
)
def test_verdict_for(
    errored: bool,
    violations: tuple,
    warn_only: bool,
    expected: str,
) -> None:
    assert verdict_for(violations, errored=errored, warn_only=warn_only) == expected


def test_survivability_score_full() -> None:
    score = compute_survivability_score(
        operations_completed=100,
        operations_failed=0,
        overload_transitions=0,
        emergency_actions=0,
        websocket_disconnects=0,
    )
    assert score == 1.0


def test_survivability_score_penalties_apply() -> None:
    base = compute_survivability_score(
        operations_completed=100,
        operations_failed=0,
        overload_transitions=0,
        emergency_actions=0,
        websocket_disconnects=0,
    )
    with_failures = compute_survivability_score(
        operations_completed=50,
        operations_failed=50,
        overload_transitions=0,
        emergency_actions=0,
        websocket_disconnects=0,
    )
    with_emergency = compute_survivability_score(
        operations_completed=100,
        operations_failed=0,
        overload_transitions=0,
        emergency_actions=4,
        websocket_disconnects=0,
    )
    assert 0.0 <= with_failures < base
    assert with_emergency < base


def test_survivability_score_is_clamped() -> None:
    score = compute_survivability_score(
        operations_completed=0,
        operations_failed=100_000,
        overload_transitions=1000,
        emergency_actions=1000,
        websocket_disconnects=10_000,
    )
    assert 0.0 <= score <= 1.0
