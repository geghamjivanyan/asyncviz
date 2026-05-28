"""Aggregated scalability report.

Given a sequence of :class:`StressOutcome` the report produces:

* a single :class:`ScalabilitySummary` with totals + worst-case
  per-metric values,
* a per-category breakdown,
* a human-readable text rendering for CI logs,
* a JSON-shaped dict for dashboards.

Pure module — no I/O beyond the JSON dict construction.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from asyncviz.stress.models.stress_outcome import StressOutcome


@dataclass(frozen=True, slots=True)
class CategoryRollup:
    category: str
    scenarios: int
    passed: int
    warned: int
    failed: int
    errored: int
    skipped: int
    operations_completed: int
    operations_failed: int
    survivability_score_mean: float


@dataclass(frozen=True, slots=True)
class ScalabilitySummary:
    scenarios: int
    passed: int
    warned: int
    failed: int
    errored: int
    skipped: int
    total_duration_s: float
    operations_completed: int
    operations_failed: int
    overload_transitions: int
    emergency_actions: int
    websocket_disconnects: int
    replay_frames_streamed: int
    render_frames_rendered: int
    peak_memory_bytes: int
    survivability_score_mean: float
    violations_total: int


@dataclass(frozen=True, slots=True)
class ScalabilityReport:
    summary: ScalabilitySummary
    by_category: tuple[CategoryRollup, ...]
    outcomes: tuple[StressOutcome, ...]

    def passed(self) -> bool:
        return self.summary.failed == 0 and self.summary.errored == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": _dataclass_dict(self.summary),
            "by_category": [_dataclass_dict(r) for r in self.by_category],
            "outcomes": [_outcome_dict(o) for o in self.outcomes],
        }

    def render_text(self) -> str:
        lines: list[str] = []
        lines.append("=== AsyncViz scalability report ===")
        s = self.summary
        lines.append(
            f"scenarios={s.scenarios} passed={s.passed} warned={s.warned} "
            f"failed={s.failed} errored={s.errored} skipped={s.skipped}",
        )
        lines.append(
            f"operations completed={s.operations_completed} failed={s.operations_failed} "
            f"survivability_mean={s.survivability_score_mean:.3f}",
        )
        lines.append(
            f"overload_transitions={s.overload_transitions} "
            f"emergency_actions={s.emergency_actions} "
            f"ws_disconnects={s.websocket_disconnects} "
            f"peak_memory={s.peak_memory_bytes} B",
        )
        lines.append(f"total_duration={s.total_duration_s:.3f}s violations={s.violations_total}")
        for rollup in self.by_category:
            lines.append(
                f"  [{rollup.category}] passed={rollup.passed} failed={rollup.failed} "
                f"warned={rollup.warned} errored={rollup.errored} "
                f"score={rollup.survivability_score_mean:.3f}",
            )
        for outcome in self.outcomes:
            badge = {
                "passed": "✓",
                "warned": "!",
                "failed": "✗",
                "errored": "E",
                "skipped": "-",
            }.get(outcome.verdict, "?")
            lines.append(
                f"  {badge} {outcome.spec.name}: {outcome.verdict} "
                f"ops={outcome.operations_completed} score={outcome.survivability_score:.3f}",
            )
            for violation in outcome.violations:
                lines.append(
                    f"      * {violation.metric}: observed={violation.observed:.2f} "
                    f"limit={violation.limit:.2f} — {violation.detail}",
                )
        return "\n".join(lines)


def build_scalability_report(
    outcomes: Iterable[StressOutcome],
) -> ScalabilityReport:
    outcome_tuple = tuple(outcomes)
    summary = _build_summary(outcome_tuple)
    by_category = _build_category_rollups(outcome_tuple)
    return ScalabilityReport(
        summary=summary,
        by_category=by_category,
        outcomes=outcome_tuple,
    )


def _build_summary(outcomes: tuple[StressOutcome, ...]) -> ScalabilitySummary:
    passed = warned = failed = errored = skipped = 0
    operations_completed = operations_failed = 0
    overload_transitions = emergency_actions = ws_disconnects = 0
    replay_frames = render_frames = 0
    total_duration = 0.0
    peak_memory = 0
    violations_total = 0
    score_sum = 0.0
    for outcome in outcomes:
        match outcome.verdict:
            case "passed":
                passed += 1
            case "warned":
                warned += 1
            case "failed":
                failed += 1
            case "errored":
                errored += 1
            case "skipped":
                skipped += 1
        operations_completed += outcome.operations_completed
        operations_failed += outcome.operations_failed
        overload_transitions += outcome.overload_transitions
        emergency_actions += outcome.emergency_actions
        ws_disconnects += outcome.websocket_disconnects
        replay_frames += outcome.replay_frames_streamed
        render_frames += outcome.render_frames_rendered
        total_duration += outcome.duration_s
        peak_memory = max(peak_memory, outcome.peak_memory_bytes)
        violations_total += len(outcome.violations)
        score_sum += outcome.survivability_score
    mean = score_sum / len(outcomes) if outcomes else 0.0
    return ScalabilitySummary(
        scenarios=len(outcomes),
        passed=passed,
        warned=warned,
        failed=failed,
        errored=errored,
        skipped=skipped,
        total_duration_s=total_duration,
        operations_completed=operations_completed,
        operations_failed=operations_failed,
        overload_transitions=overload_transitions,
        emergency_actions=emergency_actions,
        websocket_disconnects=ws_disconnects,
        replay_frames_streamed=replay_frames,
        render_frames_rendered=render_frames,
        peak_memory_bytes=peak_memory,
        survivability_score_mean=mean,
        violations_total=violations_total,
    )


def _build_category_rollups(
    outcomes: tuple[StressOutcome, ...],
) -> tuple[CategoryRollup, ...]:
    by_cat: dict[str, list[StressOutcome]] = {}
    for outcome in outcomes:
        by_cat.setdefault(outcome.spec.category, []).append(outcome)
    rollups: list[CategoryRollup] = []
    for category, items in sorted(by_cat.items()):
        passed = warned = failed = errored = skipped = 0
        ops_completed = ops_failed = 0
        score_sum = 0.0
        for outcome in items:
            match outcome.verdict:
                case "passed":
                    passed += 1
                case "warned":
                    warned += 1
                case "failed":
                    failed += 1
                case "errored":
                    errored += 1
                case "skipped":
                    skipped += 1
            ops_completed += outcome.operations_completed
            ops_failed += outcome.operations_failed
            score_sum += outcome.survivability_score
        rollups.append(
            CategoryRollup(
                category=category,
                scenarios=len(items),
                passed=passed,
                warned=warned,
                failed=failed,
                errored=errored,
                skipped=skipped,
                operations_completed=ops_completed,
                operations_failed=ops_failed,
                survivability_score_mean=score_sum / len(items) if items else 0.0,
            ),
        )
    return tuple(rollups)


def _dataclass_dict(obj: object) -> dict[str, Any]:
    if hasattr(obj, "__slots__"):
        return {name: getattr(obj, name) for name in obj.__slots__}  # type: ignore[union-attr]
    raise TypeError(f"object lacks __slots__: {obj!r}")


def _outcome_dict(outcome: StressOutcome) -> dict[str, Any]:
    return {
        "name": outcome.spec.name,
        "category": outcome.spec.category,
        "verdict": outcome.verdict,
        "duration_s": outcome.duration_s,
        "operations_completed": outcome.operations_completed,
        "operations_failed": outcome.operations_failed,
        "overload_transitions": outcome.overload_transitions,
        "emergency_actions": outcome.emergency_actions,
        "websocket_disconnects": outcome.websocket_disconnects,
        "replay_frames_streamed": outcome.replay_frames_streamed,
        "render_frames_rendered": outcome.render_frames_rendered,
        "peak_memory_bytes": outcome.peak_memory_bytes,
        "survivability_score": outcome.survivability_score,
        "error_detail": outcome.error_detail,
        "violations": [
            {
                "metric": v.metric,
                "observed": v.observed,
                "limit": v.limit,
                "detail": v.detail,
            }
            for v in outcome.violations
        ],
    }
