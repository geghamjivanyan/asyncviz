"""Integration-suite configuration.

Three presets cover the realistic range:

* :func:`default_config` — CI integration gate. Bounded runtime so a
  PR build doesn't take longer than the unit suite.
* :func:`lean_config` — laptop-friendly. Smaller storms, tighter
  timeouts, useful for iterating on a single scenario.
* :func:`relaxed_config` — nightly soak. Bigger storms, longer
  timeouts, full uvloop + asyncio matrix.

The integration suite is *separate from the pytest unit suite* in
the same way the stress suite is — pytest discovers the scenarios
via thin test-file wrappers, but the orchestration + bookkeeping
lives in framework modules so scenarios stay declarative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

IntegrationSeverity = Literal["light", "moderate", "heavy"]

DEFAULT_TASK_COUNT: Final[int] = 256
DEFAULT_REPLAY_FRAMES: Final[int] = 512
DEFAULT_WEBSOCKET_SUBSCRIBERS: Final[int] = 32
DEFAULT_WEBSOCKET_EVENTS: Final[int] = 256
DEFAULT_RENDER_FRAMES: Final[int] = 512
DEFAULT_RENDER_INVALIDATIONS: Final[int] = 256
DEFAULT_SCENARIO_BUDGET_S: Final[float] = 8.0
DEFAULT_DETERMINISM_RUNS: Final[int] = 2
DEFAULT_TRACE_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class IntegrationThresholds:
    """Per-scenario pass/fail thresholds for the validator."""

    max_replay_drift_ms: float | None = 50.0
    max_websocket_backlog: int | None = 2_048
    max_failure_ratio: float | None = 0.05
    """Acceptable ratio of failed operations to total operations
    inside a single scenario. ``None`` disables."""
    max_emergency_transitions: int | None = 2
    min_survivability_score: float | None = 0.90
    require_replay_determinism: bool = True
    require_uvloop_parity: bool = False
    """Set to ``True`` to fail a scenario when its uvloop run
    diverges from its asyncio run. Default ``False`` because not
    every scenario is replay-safe by construction."""


@dataclass(frozen=True, slots=True)
class IntegrationConfig:
    """Immutable integration-suite configuration."""

    severity: IntegrationSeverity = "moderate"
    task_count: int = DEFAULT_TASK_COUNT
    replay_frames: int = DEFAULT_REPLAY_FRAMES
    websocket_subscribers: int = DEFAULT_WEBSOCKET_SUBSCRIBERS
    websocket_events: int = DEFAULT_WEBSOCKET_EVENTS
    render_frames: int = DEFAULT_RENDER_FRAMES
    render_invalidations: int = DEFAULT_RENDER_INVALIDATIONS
    scenario_budget_s: float = DEFAULT_SCENARIO_BUDGET_S
    determinism_runs: int = DEFAULT_DETERMINISM_RUNS
    seed: int = 1
    trace_capacity: int = DEFAULT_TRACE_CAPACITY
    enable_tracing: bool = False
    enable_uvloop_matrix: bool = True
    thresholds: IntegrationThresholds = field(default_factory=IntegrationThresholds)


def default_config() -> IntegrationConfig:
    return IntegrationConfig()


def lean_config() -> IntegrationConfig:
    return IntegrationConfig(
        severity="light",
        task_count=64,
        replay_frames=128,
        websocket_subscribers=8,
        websocket_events=64,
        render_frames=128,
        render_invalidations=64,
        scenario_budget_s=3.0,
        determinism_runs=2,
        enable_uvloop_matrix=False,
    )


def relaxed_config() -> IntegrationConfig:
    return IntegrationConfig(
        severity="heavy",
        task_count=2_048,
        replay_frames=4_096,
        websocket_subscribers=256,
        websocket_events=1_024,
        render_frames=2_048,
        render_invalidations=1_024,
        scenario_budget_s=60.0,
        determinism_runs=3,
        enable_uvloop_matrix=True,
        thresholds=IntegrationThresholds(require_uvloop_parity=True),
    )
