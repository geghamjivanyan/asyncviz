"""Integration diagnostics builder tests."""

from __future__ import annotations

import json

from tests.integration._framework import (
    IntegrationOutcome,
    IntegrationScenarioSpec,
    IntegrationViolation,
    build_integration_report,
)


def _outcome(name: str, verdict: str, *, category: str = "runtime") -> IntegrationOutcome:
    return IntegrationOutcome(
        spec=IntegrationScenarioSpec(name=name, category=category),
        verdict=verdict,  # type: ignore[arg-type]
        duration_s=0.01,
    )


def test_report_passes_when_no_failures() -> None:
    report = build_integration_report([_outcome("a", "passed")])
    assert report.passed() is True


def test_report_fails_when_failures_present() -> None:
    report = build_integration_report(
        [_outcome("a", "passed"), _outcome("b", "failed")],
    )
    assert report.passed() is False


def test_report_renders_text() -> None:
    report = build_integration_report(
        [
            IntegrationOutcome(
                spec=IntegrationScenarioSpec(name="a", category="runtime"),
                verdict="failed",
                duration_s=0.01,
                violations=(
                    IntegrationViolation(
                        metric="determinism",
                        observed=1.0,
                        limit=0.0,
                        detail="d",
                    ),
                ),
            ),
        ],
    )
    rendered = report.render_text()
    assert "determinism" in rendered
    assert "AsyncViz integration report" in rendered


def test_report_as_dict_json_serializable() -> None:
    report = build_integration_report(
        [_outcome("a", "passed"), _outcome("b", "warned", category="replay")],
    )
    encoded = json.dumps(report.as_dict(), default=str)
    assert "passed" in encoded
    assert "replay" in encoded


def test_report_category_rollups() -> None:
    report = build_integration_report(
        [
            _outcome("a", "passed", category="runtime"),
            _outcome("b", "failed", category="runtime"),
            _outcome("c", "passed", category="replay"),
        ],
    )
    by_cat = {r.category: r for r in report.by_category}
    assert by_cat["runtime"].passed == 1
    assert by_cat["runtime"].failed == 1
    assert by_cat["replay"].passed == 1
