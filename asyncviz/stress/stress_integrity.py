"""Integrity invariants on stress outcomes.

The runner is permissive — it never raises mid-scenario. Operators
that want to *assert* outcomes are correct call these helpers from
their CI gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from asyncviz.stress.models.stress_outcome import StressOutcome

IntegrityViolationKind = Literal[
    "negative-counter",
    "duration-non-finite",
    "score-out-of-range",
    "violation-without-metric",
    "errored-without-detail",
]


class StressIntegrityError(Exception):
    """Raised when an outcome breaks an invariant."""


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    kind: IntegrityViolationKind
    detail: str


def check_outcome(outcome: StressOutcome) -> tuple[IntegrityFinding, ...]:
    findings: list[IntegrityFinding] = []
    counters = (
        ("operations_completed", outcome.operations_completed),
        ("operations_failed", outcome.operations_failed),
        ("overload_transitions", outcome.overload_transitions),
        ("emergency_actions", outcome.emergency_actions),
        ("websocket_disconnects", outcome.websocket_disconnects),
        ("replay_frames_streamed", outcome.replay_frames_streamed),
        ("render_frames_rendered", outcome.render_frames_rendered),
        ("peak_memory_bytes", outcome.peak_memory_bytes),
    )
    for name, value in counters:
        if value < 0:
            findings.append(
                IntegrityFinding(
                    kind="negative-counter",
                    detail=f"{name}={value}",
                ),
            )
    if outcome.duration_s < 0 or not _finite(outcome.duration_s):
        findings.append(
            IntegrityFinding(
                kind="duration-non-finite",
                detail=f"duration_s={outcome.duration_s}",
            ),
        )
    if not (0.0 <= outcome.survivability_score <= 1.0):
        findings.append(
            IntegrityFinding(
                kind="score-out-of-range",
                detail=f"survivability_score={outcome.survivability_score}",
            ),
        )
    for violation in outcome.violations:
        if not violation.metric:
            findings.append(
                IntegrityFinding(
                    kind="violation-without-metric",
                    detail=f"observed={violation.observed} limit={violation.limit}",
                ),
            )
    if outcome.verdict == "errored" and not outcome.error_detail:
        findings.append(
            IntegrityFinding(
                kind="errored-without-detail",
                detail=outcome.spec.name,
            ),
        )
    return tuple(findings)


def assert_outcome_clean(outcome: StressOutcome) -> None:
    findings = check_outcome(outcome)
    if findings:
        formatted = "; ".join(f"{f.kind}({f.detail})" for f in findings)
        raise StressIntegrityError(f"outcome {outcome.spec.name}: {formatted}")


def _finite(value: float) -> bool:
    return value == value and value != float("inf") and value != float("-inf")
