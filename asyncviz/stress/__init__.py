"""Canonical AsyncViz stress + scalability-validation layer.

Importing the package populates the default scenario registry with
the built-in suite. Public surface:

* :class:`StressRunner` — top-level façade.
* :class:`StressScenarioRegistry` — registry + decorator.
* :class:`StressConfig` + :func:`default_config` / :func:`lean_config`
  / :func:`relaxed_config` — configuration presets.
* :func:`build_scalability_report` + :class:`ScalabilityReport` —
  aggregation.
* :func:`build_stress_diagnostics` + :class:`StressDiagnostics` —
  one-call diagnostics.
* :class:`StressMetrics` + observability helpers.
* Failure-injection registry + every workload generator.
"""

from asyncviz.stress._builtin_scenarios import (
    register_builtin_scenarios,
    reset_builtin_flag,
)
from asyncviz.stress.failure_injection.failure_registry import (
    FailureInjectionRegistry,
    FailureSiteStats,
    StressInjectedFailure,
)
from asyncviz.stress.fixtures import build_test_context
from asyncviz.stress.harness.scenario_context import (
    ScenarioContext,
    derive_scenario_seed,
)
from asyncviz.stress.models.stress_outcome import (
    ScalabilityViolation,
    StressOutcome,
    StressVerdict,
)
from asyncviz.stress.models.stress_scenario import (
    ScenarioCategory,
    ScenarioSeverity,
    StressScenarioSpec,
)
from asyncviz.stress.models.stress_signal import (
    StressSignal,
    StressSignalKind,
)
from asyncviz.stress.scalability_reports.scalability_report import (
    CategoryRollup,
    ScalabilityReport,
    ScalabilitySummary,
    build_scalability_report,
)
from asyncviz.stress.stress_configuration import (
    DEFAULT_CANCEL_STORM_SIZE,
    DEFAULT_DEPENDENCY_DEPTH,
    DEFAULT_EXECUTOR_FANOUT,
    DEFAULT_GATHER_FANOUT,
    DEFAULT_LIFECYCLE_CHURN,
    DEFAULT_QUEUE_DEPTH,
    DEFAULT_RENDER_FLOOD_FRAMES,
    DEFAULT_RENDER_FLOOD_REGIONS,
    DEFAULT_RENDER_OVERLAY_EXPLOSION,
    DEFAULT_REPLAY_FRAME_BUDGET_MS,
    DEFAULT_REPLAY_SCRUB_HOPS,
    DEFAULT_REPLAY_STREAM_FRAMES,
    DEFAULT_SCENARIO_BUDGET_S,
    DEFAULT_SEMAPHORE_CONTENTION,
    DEFAULT_SLOW_CLIENT_RATIO,
    DEFAULT_TASK_STORM_SIZE,
    DEFAULT_TOPOLOGY_NODE_EXPLOSION,
    DEFAULT_TRACE_CAPACITY,
    DEFAULT_WEBSOCKET_EVENTS_PER_SUB,
    DEFAULT_WEBSOCKET_SUBSCRIBERS,
    FailureInjectionConfig,
    ScalabilityThresholds,
    StressConfig,
    StressSeverity,
    default_config,
    lean_config,
    relaxed_config,
)
from asyncviz.stress.stress_diagnostics import (
    StressDiagnostics,
    build_stress_diagnostics,
)
from asyncviz.stress.stress_integrity import (
    IntegrityFinding,
    IntegrityViolationKind,
    StressIntegrityError,
    assert_outcome_clean,
    check_outcome,
)
from asyncviz.stress.stress_observability import (
    StressMetrics,
    StressMetricsSnapshot,
    get_stress_metrics,
    get_stress_metrics_snapshot,
    reset_stress_metrics,
)
from asyncviz.stress.stress_registry import (
    RegisteredScenario,
    ScenarioCallable,
    StressScenarioRegistry,
    default_stress_registry,
    iter_categories,
    register_scenario,
    reset_default_registry,
    stress_scenario,
)
from asyncviz.stress.stress_runner import (
    StressRunInputs,
    StressRunner,
    iter_scenarios,
    run_default_suite,
)
from asyncviz.stress.stress_thresholds import (
    compute_survivability_score,
    evaluate_violations,
    verdict_for,
)
from asyncviz.stress.stress_tracing import (
    StressTraceEntry,
    StressTraceKind,
    clear_stress_trace,
    get_stress_trace,
    is_stress_trace_enabled,
    record_stress_trace,
    set_stress_trace_enabled,
    stress_trace_capacity,
)
from asyncviz.stress.utils.deterministic_rng import DeterministicRng
from asyncviz.stress.workload_generators import (
    SyntheticEvent,
    SyntheticTaskDescriptor,
    TopologyNode,
    generate_event_storm,
    generate_payload_storm,
    generate_task_storm,
    generate_topology_storm,
    reset_payload_cache,
    stable_payload,
)

register_builtin_scenarios()

__all__ = [
    "DEFAULT_CANCEL_STORM_SIZE",
    "DEFAULT_DEPENDENCY_DEPTH",
    "DEFAULT_EXECUTOR_FANOUT",
    "DEFAULT_GATHER_FANOUT",
    "DEFAULT_LIFECYCLE_CHURN",
    "DEFAULT_QUEUE_DEPTH",
    "DEFAULT_RENDER_FLOOD_FRAMES",
    "DEFAULT_RENDER_FLOOD_REGIONS",
    "DEFAULT_RENDER_OVERLAY_EXPLOSION",
    "DEFAULT_REPLAY_FRAME_BUDGET_MS",
    "DEFAULT_REPLAY_SCRUB_HOPS",
    "DEFAULT_REPLAY_STREAM_FRAMES",
    "DEFAULT_SCENARIO_BUDGET_S",
    "DEFAULT_SEMAPHORE_CONTENTION",
    "DEFAULT_SLOW_CLIENT_RATIO",
    "DEFAULT_TASK_STORM_SIZE",
    "DEFAULT_TOPOLOGY_NODE_EXPLOSION",
    "DEFAULT_TRACE_CAPACITY",
    "DEFAULT_WEBSOCKET_EVENTS_PER_SUB",
    "DEFAULT_WEBSOCKET_SUBSCRIBERS",
    "CategoryRollup",
    "DeterministicRng",
    "FailureInjectionConfig",
    "FailureInjectionRegistry",
    "FailureSiteStats",
    "IntegrityFinding",
    "IntegrityViolationKind",
    "RegisteredScenario",
    "ScalabilityReport",
    "ScalabilitySummary",
    "ScalabilityThresholds",
    "ScalabilityViolation",
    "ScenarioCallable",
    "ScenarioCategory",
    "ScenarioContext",
    "ScenarioSeverity",
    "StressConfig",
    "StressDiagnostics",
    "StressInjectedFailure",
    "StressIntegrityError",
    "StressMetrics",
    "StressMetricsSnapshot",
    "StressOutcome",
    "StressRunInputs",
    "StressRunner",
    "StressScenarioRegistry",
    "StressScenarioSpec",
    "StressSeverity",
    "StressSignal",
    "StressSignalKind",
    "StressTraceEntry",
    "StressTraceKind",
    "StressVerdict",
    "SyntheticEvent",
    "SyntheticTaskDescriptor",
    "TopologyNode",
    "assert_outcome_clean",
    "build_scalability_report",
    "build_stress_diagnostics",
    "build_test_context",
    "check_outcome",
    "clear_stress_trace",
    "compute_survivability_score",
    "default_config",
    "default_stress_registry",
    "derive_scenario_seed",
    "evaluate_violations",
    "generate_event_storm",
    "generate_payload_storm",
    "generate_task_storm",
    "generate_topology_storm",
    "get_stress_metrics",
    "get_stress_metrics_snapshot",
    "get_stress_trace",
    "is_stress_trace_enabled",
    "iter_categories",
    "iter_scenarios",
    "lean_config",
    "record_stress_trace",
    "register_builtin_scenarios",
    "register_scenario",
    "relaxed_config",
    "reset_builtin_flag",
    "reset_default_registry",
    "reset_payload_cache",
    "reset_stress_metrics",
    "run_default_suite",
    "set_stress_trace_enabled",
    "stable_payload",
    "stress_scenario",
    "stress_trace_capacity",
    "verdict_for",
]
