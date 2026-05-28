"""Scalability-threshold validator.

Given an in-flight :class:`StressOutcome` plus the configured
:class:`ScalabilityThresholds`, compute the list of
:class:`ScalabilityViolation` entries + the final verdict.

Pure module — no I/O, no globals.
"""

from __future__ import annotations

from asyncviz.stress.models.stress_outcome import (
    ScalabilityViolation,
    StressVerdict,
)
from asyncviz.stress.stress_configuration import ScalabilityThresholds


def evaluate_violations(
    *,
    thresholds: ScalabilityThresholds,
    dropped_frames: int = 0,
    replay_drift_ms: float = 0.0,
    websocket_backlog: int = 0,
    memory_growth_bytes: int = 0,
    fps: float | None = None,
    emergency_transitions: int = 0,
    survivability_score: float | None = None,
) -> tuple[ScalabilityViolation, ...]:
    """Return the violations a scenario triggered, in stable order."""
    violations: list[ScalabilityViolation] = []
    if (
        thresholds.max_dropped_frames is not None
        and dropped_frames > thresholds.max_dropped_frames
    ):
        violations.append(
            ScalabilityViolation(
                metric="dropped_frames",
                observed=float(dropped_frames),
                limit=float(thresholds.max_dropped_frames),
                detail="frame skips exceeded the configured ceiling",
            ),
        )
    if (
        thresholds.max_replay_drift_ms is not None
        and replay_drift_ms > thresholds.max_replay_drift_ms
    ):
        violations.append(
            ScalabilityViolation(
                metric="replay_drift_ms",
                observed=float(replay_drift_ms),
                limit=float(thresholds.max_replay_drift_ms),
                detail="replay diverged from expected timing",
            ),
        )
    if (
        thresholds.max_websocket_backlog is not None
        and websocket_backlog > thresholds.max_websocket_backlog
    ):
        violations.append(
            ScalabilityViolation(
                metric="websocket_backlog",
                observed=float(websocket_backlog),
                limit=float(thresholds.max_websocket_backlog),
                detail="websocket backlog exceeded configured ceiling",
            ),
        )
    if (
        thresholds.max_memory_growth_bytes is not None
        and memory_growth_bytes > thresholds.max_memory_growth_bytes
    ):
        violations.append(
            ScalabilityViolation(
                metric="memory_growth_bytes",
                observed=float(memory_growth_bytes),
                limit=float(thresholds.max_memory_growth_bytes),
                detail="memory grew beyond the configured ceiling",
            ),
        )
    if (
        thresholds.min_fps is not None
        and fps is not None
        and fps < thresholds.min_fps
    ):
        violations.append(
            ScalabilityViolation(
                metric="fps",
                observed=float(fps),
                limit=float(thresholds.min_fps),
                detail="FPS dropped below the configured minimum",
            ),
        )
    if (
        thresholds.max_emergency_transitions is not None
        and emergency_transitions > thresholds.max_emergency_transitions
    ):
        violations.append(
            ScalabilityViolation(
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
            ScalabilityViolation(
                metric="survivability_score",
                observed=float(survivability_score),
                limit=float(thresholds.min_survivability_score),
                detail="survivability score below the configured minimum",
            ),
        )
    return tuple(violations)


def verdict_for(
    violations: tuple[ScalabilityViolation, ...],
    *,
    errored: bool = False,
    warn_only: bool = False,
) -> StressVerdict:
    """Map violations to the canonical verdict.

    * an exception → ``errored``
    * any violations + ``warn_only=True`` → ``warned``
    * any violations otherwise → ``failed``
    * no violations → ``passed``
    """
    if errored:
        return "errored"
    if not violations:
        return "passed"
    return "warned" if warn_only else "failed"


def compute_survivability_score(
    *,
    operations_completed: int,
    operations_failed: int,
    overload_transitions: int,
    emergency_actions: int,
    websocket_disconnects: int,
) -> float:
    """Heuristic 0.0..1.0 score.

    Mathematically:

        score = base - failure_penalty - overload_penalty - disconnect_penalty

    where every term is clamped + bounded so a single bad signal can't
    drive the score negative. The score is *informational* — the
    validator uses it but operators are encouraged to look at the raw
    counters as well.
    """
    total = max(1, operations_completed + operations_failed)
    failure_ratio = operations_failed / total
    base = 1.0
    failure_penalty = min(0.5, failure_ratio * 0.75)
    overload_penalty = min(0.2, overload_transitions * 0.02)
    emergency_penalty = min(0.2, emergency_actions * 0.05)
    disconnect_penalty = min(0.2, websocket_disconnects * 0.005)
    score = base - failure_penalty - overload_penalty - emergency_penalty - disconnect_penalty
    return max(0.0, min(1.0, score))
