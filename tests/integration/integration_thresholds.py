"""Integration threshold validator."""

from __future__ import annotations

from asyncviz.stress.stress_thresholds import (  # type: ignore[import-not-found]
    compute_survivability_score as _stress_score,
)
from tests.integration.integration_configuration import IntegrationThresholds
from tests.integration.integration_models import (
    IntegrationVerdict,
    IntegrationViolation,
)


def evaluate_violations(
    *,
    thresholds: IntegrationThresholds,
    operations_completed: int = 0,
    operations_failed: int = 0,
    replay_drift_ms: float = 0.0,
    websocket_backlog: int = 0,
    emergency_transitions: int = 0,
    survivability_score: float | None = None,
    determinism_diverged: bool = False,
    uvloop_diverged: bool = False,
) -> tuple[IntegrationViolation, ...]:
    violations: list[IntegrationViolation] = []
    total = max(1, operations_completed + operations_failed)
    failure_ratio = operations_failed / total
    if (
        thresholds.max_failure_ratio is not None
        and failure_ratio > thresholds.max_failure_ratio
    ):
        violations.append(
            IntegrationViolation(
                metric="failure_ratio",
                observed=failure_ratio,
                limit=thresholds.max_failure_ratio,
                detail="operations_failed/total exceeded ceiling",
            ),
        )
    if (
        thresholds.max_replay_drift_ms is not None
        and replay_drift_ms > thresholds.max_replay_drift_ms
    ):
        violations.append(
            IntegrationViolation(
                metric="replay_drift_ms",
                observed=replay_drift_ms,
                limit=thresholds.max_replay_drift_ms,
                detail="replay diverged from baseline timing",
            ),
        )
    if (
        thresholds.max_websocket_backlog is not None
        and websocket_backlog > thresholds.max_websocket_backlog
    ):
        violations.append(
            IntegrationViolation(
                metric="websocket_backlog",
                observed=float(websocket_backlog),
                limit=float(thresholds.max_websocket_backlog),
                detail="backlog exceeded ceiling",
            ),
        )
    if (
        thresholds.max_emergency_transitions is not None
        and emergency_transitions > thresholds.max_emergency_transitions
    ):
        violations.append(
            IntegrationViolation(
                metric="emergency_transitions",
                observed=float(emergency_transitions),
                limit=float(thresholds.max_emergency_transitions),
                detail="too many emergency-mode entries",
            ),
        )
    if (
        thresholds.min_survivability_score is not None
        and survivability_score is not None
        and survivability_score < thresholds.min_survivability_score
    ):
        violations.append(
            IntegrationViolation(
                metric="survivability_score",
                observed=survivability_score,
                limit=thresholds.min_survivability_score,
                detail="survivability score below the configured minimum",
            ),
        )
    if thresholds.require_replay_determinism and determinism_diverged:
        violations.append(
            IntegrationViolation(
                metric="determinism",
                observed=1.0,
                limit=0.0,
                detail="two replay runs produced different outputs",
            ),
        )
    if thresholds.require_uvloop_parity and uvloop_diverged:
        violations.append(
            IntegrationViolation(
                metric="uvloop_parity",
                observed=1.0,
                limit=0.0,
                detail="uvloop run diverged from asyncio run",
            ),
        )
    return tuple(violations)


def verdict_for(
    violations: tuple[IntegrationViolation, ...],
    *,
    errored: bool = False,
    warn_only: bool = False,
) -> IntegrationVerdict:
    if errored:
        return "errored"
    if not violations:
        return "passed"
    return "warned" if warn_only else "failed"


def compute_survivability_score(
    *,
    operations_completed: int,
    operations_failed: int,
    overload_transitions: int = 0,
    emergency_actions: int = 0,
    websocket_disconnects: int = 0,
) -> float:
    """Re-export the stress survivability formula so the integration
    suite shares a single notion of "how degraded was this run"."""
    return _stress_score(
        operations_completed=operations_completed,
        operations_failed=operations_failed,
        overload_transitions=overload_transitions,
        emergency_actions=emergency_actions,
        websocket_disconnects=websocket_disconnects,
    )
