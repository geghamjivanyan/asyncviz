"""Value models for the integration framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

IntegrationCategory = Literal[
    "runtime",
    "replay",
    "websocket",
    "rendering",
    "resilience",
    "overload",
    "uvloop",
    "stress",
    "topology",
    "observability",
    "diagnostics",
]

IntegrationVerdict = Literal["passed", "warned", "failed", "errored", "skipped"]


@dataclass(frozen=True, slots=True)
class IntegrationScenarioSpec:
    """Declarative description of one end-to-end scenario."""

    name: str
    category: IntegrationCategory
    description: str = ""
    replay_safe: bool = True
    uvloop_safe: bool = True
    require_determinism: bool = True


@dataclass(frozen=True, slots=True)
class IntegrationViolation:
    metric: str
    observed: float
    limit: float
    detail: str = ""


@dataclass(frozen=True, slots=True)
class IntegrationOutcome:
    spec: IntegrationScenarioSpec
    verdict: IntegrationVerdict
    duration_s: float
    operations_completed: int = 0
    operations_failed: int = 0
    replay_drift_ms: float = 0.0
    websocket_backlog_peak: int = 0
    replay_frames: int = 0
    render_frames: int = 0
    render_drops: int = 0
    overload_transitions: int = 0
    emergency_transitions: int = 0
    survivability_score: float = 1.0
    determinism_runs: int = 0
    determinism_diverged: bool = False
    uvloop_matrix_run: bool = False
    uvloop_diverged: bool = False
    violations: tuple[IntegrationViolation, ...] = ()
    error_detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
