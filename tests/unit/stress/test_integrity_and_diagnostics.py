"""Integrity + diagnostics tests."""

from __future__ import annotations

import pytest

from asyncviz.stress import (
    ScalabilityViolation,
    StressIntegrityError,
    StressOutcome,
    StressScenarioSpec,
    assert_outcome_clean,
    build_stress_diagnostics,
    check_outcome,
    get_stress_metrics,
    set_stress_trace_enabled,
)


def _outcome(**kwargs) -> StressOutcome:
    return StressOutcome(
        spec=StressScenarioSpec(name="x", category="task"),
        verdict="passed",
        duration_s=0.1,
        **kwargs,
    )


def test_check_clean_outcome() -> None:
    out = _outcome()
    assert check_outcome(out) == ()
    assert_outcome_clean(out)


def test_negative_counter_is_flagged() -> None:
    out = _outcome(operations_failed=-1)
    findings = check_outcome(out)
    assert any(f.kind == "negative-counter" for f in findings)


def test_survivability_out_of_range_flagged() -> None:
    out = _outcome(survivability_score=1.5)
    findings = check_outcome(out)
    assert any(f.kind == "score-out-of-range" for f in findings)


def test_errored_without_detail_flagged() -> None:
    out = StressOutcome(
        spec=StressScenarioSpec(name="x", category="task"),
        verdict="errored",
        duration_s=0.1,
        error_detail="",
    )
    findings = check_outcome(out)
    assert any(f.kind == "errored-without-detail" for f in findings)


def test_assert_outcome_clean_raises() -> None:
    out = _outcome(operations_failed=-5)
    with pytest.raises(StressIntegrityError):
        assert_outcome_clean(out)


def test_violation_without_metric_flagged() -> None:
    out = _outcome(violations=(ScalabilityViolation(metric="", observed=0, limit=0, detail=""),))
    findings = check_outcome(out)
    assert any(f.kind == "violation-without-metric" for f in findings)


def test_duration_non_finite_flagged() -> None:
    out = StressOutcome(
        spec=StressScenarioSpec(name="x", category="task"),
        verdict="passed",
        duration_s=float("nan"),
    )
    findings = check_outcome(out)
    assert any(f.kind == "duration-non-finite" for f in findings)


def test_diagnostics_returns_snapshot() -> None:
    get_stress_metrics().record_operation_completed(3)
    diag = build_stress_diagnostics()
    assert diag.metrics.operations_completed >= 3
    assert diag.report is None


def test_diagnostics_includes_trace() -> None:
    set_stress_trace_enabled(True)
    try:
        from asyncviz.stress import record_stress_trace

        record_stress_trace("signal", "diag-detail")
        diag = build_stress_diagnostics(trace_limit=8)
        assert any(entry.detail == "diag-detail" for entry in diag.trace)
    finally:
        set_stress_trace_enabled(False)
