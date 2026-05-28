"""Stress-test configuration.

Owns every knob the canonical stress-validation layer cares about:
storm sizes, time budgets, failure-injection toggles, threshold
tolerances. Three presets cover the realistic range:

* :func:`default_config` — tuned for the CI scalability gate.
* :func:`lean_config`    — small, fast, runs in seconds; for fast
  iteration on a laptop.
* :func:`relaxed_config` — large + slow; for nightly soak runs.

The configuration is *value-only*: no methods, no globals. Stress
scenarios read it at construction time and never mutate it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

StressSeverity = Literal["light", "moderate", "heavy", "extreme"]
"""Coarse storm severity. Drives default storm-size selection."""

DEFAULT_TASK_STORM_SIZE: Final[int] = 10_000
DEFAULT_LIFECYCLE_CHURN: Final[int] = 50_000
DEFAULT_CANCEL_STORM_SIZE: Final[int] = 5_000
DEFAULT_GATHER_FANOUT: Final[int] = 256
DEFAULT_DEPENDENCY_DEPTH: Final[int] = 16

DEFAULT_WEBSOCKET_SUBSCRIBERS: Final[int] = 1_024
DEFAULT_WEBSOCKET_EVENTS_PER_SUB: Final[int] = 256
DEFAULT_SLOW_CLIENT_RATIO: Final[float] = 0.05
DEFAULT_REPLAY_STREAM_FRAMES: Final[int] = 8_192

DEFAULT_REPLAY_SCRUB_HOPS: Final[int] = 1_024
DEFAULT_REPLAY_FRAME_BUDGET_MS: Final[float] = 25.0

DEFAULT_RENDER_FLOOD_FRAMES: Final[int] = 4_096
DEFAULT_RENDER_FLOOD_REGIONS: Final[int] = 2_048
DEFAULT_RENDER_OVERLAY_EXPLOSION: Final[int] = 4_096

DEFAULT_EXECUTOR_FANOUT: Final[int] = 1_024
DEFAULT_QUEUE_DEPTH: Final[int] = 32_768
DEFAULT_SEMAPHORE_CONTENTION: Final[int] = 1_024
DEFAULT_TOPOLOGY_NODE_EXPLOSION: Final[int] = 8_192

DEFAULT_SCENARIO_BUDGET_S: Final[float] = 30.0
"""Hard upper bound on a single scenario's wall-clock cost."""

DEFAULT_TRACE_CAPACITY: Final[int] = 256
"""Ring-buffer entries retained for stress tracing."""


@dataclass(frozen=True, slots=True)
class FailureInjectionConfig:
    """Toggles for the failure-injection registry.

    ``injection_rate`` is the *fraction* of operations a registered
    fault is applied to. The registry uses it deterministically: with
    a stable seed, replays produce identical fault placement.
    """

    enabled: bool = False
    injection_rate: float = 0.05
    seed: int = 1
    websocket_disconnects: bool = True
    reducer_exceptions: bool = True
    replay_corruption: bool = False
    serialization_failures: bool = True
    queue_saturation: bool = True
    topology_explosions: bool = False


@dataclass(frozen=True, slots=True)
class ScalabilityThresholds:
    """Per-storm pass/fail thresholds for the validator.

    The default values are conservative — most CI gates will widen
    them slightly. Set any field to ``None`` to disable the
    corresponding assertion.
    """

    max_dropped_frames: int | None = 64
    max_replay_drift_ms: float | None = 50.0
    max_websocket_backlog: int | None = 4_096
    max_memory_growth_bytes: int | None = 64 * 1024 * 1024
    min_fps: float | None = 30.0
    max_emergency_transitions: int | None = 4
    min_survivability_score: float | None = 0.85
    """0.0..1.0 score covering recovery, replay determinism, and
    bounded resource usage. See :mod:`stress_thresholds`."""


@dataclass(frozen=True, slots=True)
class StressConfig:
    """Immutable stress-suite configuration."""

    severity: StressSeverity = "moderate"
    task_storm_size: int = DEFAULT_TASK_STORM_SIZE
    lifecycle_churn: int = DEFAULT_LIFECYCLE_CHURN
    cancel_storm_size: int = DEFAULT_CANCEL_STORM_SIZE
    gather_fanout: int = DEFAULT_GATHER_FANOUT
    dependency_depth: int = DEFAULT_DEPENDENCY_DEPTH
    websocket_subscribers: int = DEFAULT_WEBSOCKET_SUBSCRIBERS
    websocket_events_per_subscriber: int = DEFAULT_WEBSOCKET_EVENTS_PER_SUB
    slow_client_ratio: float = DEFAULT_SLOW_CLIENT_RATIO
    replay_stream_frames: int = DEFAULT_REPLAY_STREAM_FRAMES
    replay_scrub_hops: int = DEFAULT_REPLAY_SCRUB_HOPS
    replay_frame_budget_ms: float = DEFAULT_REPLAY_FRAME_BUDGET_MS
    render_flood_frames: int = DEFAULT_RENDER_FLOOD_FRAMES
    render_flood_regions: int = DEFAULT_RENDER_FLOOD_REGIONS
    render_overlay_explosion: int = DEFAULT_RENDER_OVERLAY_EXPLOSION
    executor_fanout: int = DEFAULT_EXECUTOR_FANOUT
    queue_depth: int = DEFAULT_QUEUE_DEPTH
    semaphore_contention: int = DEFAULT_SEMAPHORE_CONTENTION
    topology_node_explosion: int = DEFAULT_TOPOLOGY_NODE_EXPLOSION
    scenario_budget_s: float = DEFAULT_SCENARIO_BUDGET_S
    trace_capacity: int = DEFAULT_TRACE_CAPACITY
    failure_injection: FailureInjectionConfig = field(
        default_factory=FailureInjectionConfig,
    )
    thresholds: ScalabilityThresholds = field(
        default_factory=ScalabilityThresholds,
    )


def default_config() -> StressConfig:
    """CI-grade scalability gate."""
    return StressConfig()


def lean_config() -> StressConfig:
    """Small, fast — useful on a laptop or quick PR."""
    return StressConfig(
        severity="light",
        task_storm_size=1_000,
        lifecycle_churn=2_000,
        cancel_storm_size=500,
        gather_fanout=32,
        dependency_depth=4,
        websocket_subscribers=128,
        websocket_events_per_subscriber=64,
        slow_client_ratio=0.05,
        replay_stream_frames=1_024,
        replay_scrub_hops=128,
        replay_frame_budget_ms=25.0,
        render_flood_frames=512,
        render_flood_regions=256,
        render_overlay_explosion=512,
        executor_fanout=128,
        queue_depth=4_096,
        semaphore_contention=128,
        topology_node_explosion=1_024,
        scenario_budget_s=10.0,
    )


def relaxed_config() -> StressConfig:
    """Heavy, soak-style — for nightly runs."""
    return StressConfig(
        severity="extreme",
        task_storm_size=100_000,
        lifecycle_churn=500_000,
        cancel_storm_size=50_000,
        gather_fanout=2_048,
        dependency_depth=64,
        websocket_subscribers=8_192,
        websocket_events_per_subscriber=4_096,
        slow_client_ratio=0.10,
        replay_stream_frames=65_536,
        replay_scrub_hops=8_192,
        replay_frame_budget_ms=33.0,
        render_flood_frames=32_768,
        render_flood_regions=16_384,
        render_overlay_explosion=32_768,
        executor_fanout=8_192,
        queue_depth=262_144,
        semaphore_contention=8_192,
        topology_node_explosion=65_536,
        scenario_budget_s=300.0,
    )
