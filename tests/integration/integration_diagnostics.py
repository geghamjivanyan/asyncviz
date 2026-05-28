"""Aggregated integration-suite diagnostics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from tests.integration.integration_models import IntegrationOutcome
from tests.integration.integration_observability import (
    IntegrationMetricsSnapshot,
    get_integration_metrics_snapshot,
)
from tests.integration.integration_tracing import (
    IntegrationTraceEntry,
    get_integration_trace,
)


@dataclass(frozen=True, slots=True)
class CategoryRollup:
    category: str
    scenarios: int
    passed: int
    warned: int
    failed: int
    errored: int


@dataclass(frozen=True, slots=True)
class IntegrationReport:
    metrics: IntegrationMetricsSnapshot
    outcomes: tuple[IntegrationOutcome, ...]
    by_category: tuple[CategoryRollup, ...]
    trace: tuple[IntegrationTraceEntry, ...]

    def passed(self) -> bool:
        return not any(
            outcome.verdict in ("failed", "errored") for outcome in self.outcomes
        )

    def render_text(self) -> str:
        lines = [
            "=== AsyncViz integration report ===",
            f"scenarios={self.metrics.scenarios_completed} "
            f"passed={self.metrics.scenarios_passed} "
            f"warned={self.metrics.scenarios_warned} "
            f"failed={self.metrics.scenarios_failed} "
            f"errored={self.metrics.scenarios_errored} "
            f"skipped={self.metrics.scenarios_skipped}",
            f"operations completed={self.metrics.operations_completed} "
            f"failed={self.metrics.operations_failed} "
            f"violations={self.metrics.threshold_violations}",
            f"determinism_runs={self.metrics.determinism_runs} "
            f"diverged={self.metrics.determinism_divergences} "
            f"uvloop_runs={self.metrics.uvloop_matrix_runs} "
            f"uvloop_diverged={self.metrics.uvloop_divergences}",
        ]
        for rollup in self.by_category:
            lines.append(
                f"  [{rollup.category}] passed={rollup.passed} "
                f"warned={rollup.warned} failed={rollup.failed} "
                f"errored={rollup.errored}",
            )
        for outcome in self.outcomes:
            badge = {
                "passed": "+",
                "warned": "!",
                "failed": "X",
                "errored": "E",
                "skipped": "-",
            }.get(outcome.verdict, "?")
            lines.append(
                f"  {badge} {outcome.spec.name}: {outcome.verdict} "
                f"ops={outcome.operations_completed} "
                f"failures={outcome.operations_failed}",
            )
            for violation in outcome.violations:
                lines.append(
                    f"      * {violation.metric}: observed={violation.observed:.3f} "
                    f"limit={violation.limit:.3f} — {violation.detail}",
                )
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenarios": self.metrics.scenarios_completed,
            "passed": self.metrics.scenarios_passed,
            "warned": self.metrics.scenarios_warned,
            "failed": self.metrics.scenarios_failed,
            "errored": self.metrics.scenarios_errored,
            "skipped": self.metrics.scenarios_skipped,
            "by_category": [
                {
                    "category": r.category,
                    "scenarios": r.scenarios,
                    "passed": r.passed,
                    "warned": r.warned,
                    "failed": r.failed,
                    "errored": r.errored,
                }
                for r in self.by_category
            ],
            "outcomes": [
                {
                    "name": o.spec.name,
                    "category": o.spec.category,
                    "verdict": o.verdict,
                    "operations_completed": o.operations_completed,
                    "operations_failed": o.operations_failed,
                    "survivability_score": o.survivability_score,
                    "determinism_diverged": o.determinism_diverged,
                    "uvloop_diverged": o.uvloop_diverged,
                    "violations": [
                        {
                            "metric": v.metric,
                            "observed": v.observed,
                            "limit": v.limit,
                            "detail": v.detail,
                        }
                        for v in o.violations
                    ],
                }
                for o in self.outcomes
            ],
        }


def build_integration_report(
    outcomes: Iterable[IntegrationOutcome],
    *,
    trace_limit: int = 64,
) -> IntegrationReport:
    outcomes_tuple = tuple(outcomes)
    by_cat: dict[str, list[IntegrationOutcome]] = {}
    for outcome in outcomes_tuple:
        by_cat.setdefault(outcome.spec.category, []).append(outcome)
    rollups: list[CategoryRollup] = []
    for category in sorted(by_cat):
        items = by_cat[category]
        rollups.append(
            CategoryRollup(
                category=category,
                scenarios=len(items),
                passed=sum(1 for o in items if o.verdict == "passed"),
                warned=sum(1 for o in items if o.verdict == "warned"),
                failed=sum(1 for o in items if o.verdict == "failed"),
                errored=sum(1 for o in items if o.verdict == "errored"),
            ),
        )
    trace = get_integration_trace()
    if trace_limit > 0 and len(trace) > trace_limit:
        trace = trace[-trace_limit:]
    return IntegrationReport(
        metrics=get_integration_metrics_snapshot(),
        outcomes=outcomes_tuple,
        by_category=tuple(rollups),
        trace=trace,
    )
