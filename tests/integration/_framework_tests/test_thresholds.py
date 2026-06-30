"""Threshold-validator tests."""

from __future__ import annotations

from tests.integration._framework import (
    IntegrationThresholds,
    compute_survivability_score,
    evaluate_violations,
    verdict_for,
)


def test_no_violations_below_limits() -> None:
    violations = evaluate_violations(
        thresholds=IntegrationThresholds(),
        operations_completed=100,
        operations_failed=0,
        survivability_score=1.0,
    )
    assert violations == ()


def test_failure_ratio_violation() -> None:
    violations = evaluate_violations(
        thresholds=IntegrationThresholds(max_failure_ratio=0.1),
        operations_completed=10,
        operations_failed=10,
    )
    assert any(v.metric == "failure_ratio" for v in violations)


def test_determinism_violation_when_required() -> None:
    violations = evaluate_violations(
        thresholds=IntegrationThresholds(require_replay_determinism=True),
        determinism_diverged=True,
    )
    assert any(v.metric == "determinism" for v in violations)


def test_uvloop_parity_violation_when_required() -> None:
    violations = evaluate_violations(
        thresholds=IntegrationThresholds(require_uvloop_parity=True),
        uvloop_diverged=True,
    )
    assert any(v.metric == "uvloop_parity" for v in violations)


def test_uvloop_parity_ignored_when_not_required() -> None:
    violations = evaluate_violations(
        thresholds=IntegrationThresholds(require_uvloop_parity=False),
        uvloop_diverged=True,
    )
    assert all(v.metric != "uvloop_parity" for v in violations)


def test_verdict_mapping() -> None:
    assert verdict_for(()) == "passed"
    assert verdict_for(((),)) in ("failed", "warned")  # type: ignore[arg-type]
    assert verdict_for((), errored=True) == "errored"


def test_survivability_score_re_exports_stress_formula() -> None:
    a = compute_survivability_score(
        operations_completed=100,
        operations_failed=0,
    )
    b = compute_survivability_score(
        operations_completed=50,
        operations_failed=50,
    )
    assert a == 1.0
    assert b < a
