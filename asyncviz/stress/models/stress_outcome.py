"""Stress-scenario outcome value model.

The runner produces one :class:`StressOutcome` per scenario. The
outcome captures everything the validator + reports + diagnostics
need: timing, counters, failures, threshold validations, and the
collected sub-system metrics.

Outcomes are frozen — they're meant to be safely stashed in a JSON
artifact + replayed for trend analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from asyncviz.stress.models.stress_scenario import StressScenarioSpec

StressVerdict = Literal["passed", "warned", "failed", "errored", "skipped"]


@dataclass(frozen=True, slots=True)
class ScalabilityViolation:
    """Single threshold breach observed during a scenario."""

    metric: str
    observed: float
    limit: float
    detail: str = ""


@dataclass(frozen=True, slots=True)
class StressOutcome:
    """Result of running one :class:`StressScenarioSpec`."""

    spec: StressScenarioSpec
    verdict: StressVerdict
    duration_s: float
    operations_completed: int = 0
    operations_failed: int = 0
    overload_transitions: int = 0
    emergency_actions: int = 0
    websocket_disconnects: int = 0
    replay_frames_streamed: int = 0
    render_frames_rendered: int = 0
    peak_memory_bytes: int = 0
    survivability_score: float = 1.0
    """0.0..1.0. 1.0 means "no degradation observed"."""
    violations: tuple[ScalabilityViolation, ...] = ()
    error_detail: str = ""
    extra_metrics: dict[str, Any] = field(default_factory=dict)
