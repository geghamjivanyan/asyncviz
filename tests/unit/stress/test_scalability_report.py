"""Scalability report tests."""

from __future__ import annotations

from asyncviz.stress import (
    ScalabilityViolation,
    StressOutcome,
    StressScenarioSpec,
    build_scalability_report,
)


def _spec(name: str, category: str = "task") -> StressScenarioSpec:
    return StressScenarioSpec(name=name, category=category)


def _outcome(
    *,
    name: str,
    verdict: str,
    category: str = "task",
    ops: int = 100,
    failures: int = 0,
    score: float = 1.0,
    violations: tuple[ScalabilityViolation, ...] = (),
) -> StressOutcome:
    return StressOutcome(
        spec=_spec(name, category),
        verdict=verdict,  # type: ignore[arg-type]
        duration_s=0.1,
        operations_completed=ops,
        operations_failed=failures,
        survivability_score=score,
        violations=violations,
    )


def test_empty_report() -> None:
    report = build_scalability_report([])
    assert report.summary.scenarios == 0
    assert report.passed() is True


def test_report_counts_by_verdict() -> None:
    outcomes = [
        _outcome(name="a", verdict="passed"),
        _outcome(name="b", verdict="warned"),
        _outcome(name="c", verdict="failed"),
        _outcome(name="d", verdict="errored"),
        _outcome(name="e", verdict="skipped"),
    ]
    report = build_scalability_report(outcomes)
    assert report.summary.passed == 1
    assert report.summary.warned == 1
    assert report.summary.failed == 1
    assert report.summary.errored == 1
    assert report.summary.skipped == 1
    assert not report.passed()


def test_report_aggregates_ops_and_survivability() -> None:
    outcomes = [
        _outcome(name="a", verdict="passed", ops=10, score=0.9),
        _outcome(name="b", verdict="passed", ops=20, score=0.5),
    ]
    report = build_scalability_report(outcomes)
    assert report.summary.operations_completed == 30
    assert report.summary.survivability_score_mean == 0.7


def test_report_category_rollups() -> None:
    outcomes = [
        _outcome(name="a", verdict="passed", category="task"),
        _outcome(name="b", verdict="failed", category="task"),
        _outcome(name="c", verdict="passed", category="websocket"),
    ]
    report = build_scalability_report(outcomes)
    by_cat = {r.category: r for r in report.by_category}
    assert by_cat["task"].passed == 1
    assert by_cat["task"].failed == 1
    assert by_cat["websocket"].passed == 1


def test_as_dict_is_json_serializable() -> None:
    import json

    outcomes = [
        _outcome(
            name="a",
            verdict="failed",
            violations=(
                ScalabilityViolation(metric="x", observed=5.0, limit=3.0, detail="too high"),
            ),
        ),
    ]
    report = build_scalability_report(outcomes)
    data = report.as_dict()
    encoded = json.dumps(data, default=str)
    assert "x" in encoded


def test_render_text_includes_violations() -> None:
    outcomes = [
        _outcome(
            name="a",
            verdict="failed",
            violations=(
                ScalabilityViolation(metric="fps", observed=10.0, limit=30.0, detail="low"),
            ),
        ),
    ]
    report = build_scalability_report(outcomes)
    rendered = report.render_text()
    assert "fps" in rendered
    assert "low" in rendered
