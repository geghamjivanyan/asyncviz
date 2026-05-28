"""Canonical integration framework barrel.

Importing this module:

* populates the default :class:`IntegrationRegistry` with every
  built-in scenario,
* re-exports the public surface (config + runner + report + models +
  fixtures + harness) so tests have a single import path.

Tests that want a fully-clean registry import this module then call
:func:`reset_default_registry` before adding their own.
"""

from tests.integration.fixtures import build_test_context, lean_test_config
from tests.integration.harness.scenario_context import (
    IntegrationContext,
    IntegrationSignal,
    IntegrationSignalKind,
    derive_scenario_seed,
)
from tests.integration.harness.scenario_runner import (
    ScenarioCallable,
    run_scenario_async,
)
from tests.integration.integration_configuration import (
    DEFAULT_DETERMINISM_RUNS,
    DEFAULT_RENDER_FRAMES,
    DEFAULT_REPLAY_FRAMES,
    DEFAULT_SCENARIO_BUDGET_S,
    DEFAULT_TASK_COUNT,
    DEFAULT_TRACE_CAPACITY,
    DEFAULT_WEBSOCKET_EVENTS,
    DEFAULT_WEBSOCKET_SUBSCRIBERS,
    IntegrationConfig,
    IntegrationSeverity,
    IntegrationThresholds,
    default_config,
    lean_config,
    relaxed_config,
)
from tests.integration.integration_diagnostics import (
    CategoryRollup,
    IntegrationReport,
    build_integration_report,
)
from tests.integration.integration_models import (
    IntegrationCategory,
    IntegrationOutcome,
    IntegrationScenarioSpec,
    IntegrationVerdict,
    IntegrationViolation,
)
from tests.integration.integration_observability import (
    IntegrationMetrics,
    IntegrationMetricsSnapshot,
    get_integration_metrics,
    get_integration_metrics_snapshot,
    reset_integration_metrics,
)
from tests.integration.integration_registry import (
    IntegrationRegistry,
    RegisteredScenario,
    default_integration_registry,
    register_scenario,
    reset_default_registry,
)
from tests.integration.integration_runner import (
    IntegrationRunInputs,
    IntegrationRunner,
    iter_scenarios,
    run_default_suite,
    run_default_suite_sync,
)
from tests.integration.integration_thresholds import (
    compute_survivability_score,
    evaluate_violations,
    verdict_for,
)
from tests.integration.integration_tracing import (
    IntegrationTraceEntry,
    IntegrationTraceKind,
    clear_integration_trace,
    get_integration_trace,
    integration_trace_capacity,
    is_integration_trace_enabled,
    record_integration_trace,
    set_integration_trace_enabled,
)
from tests.integration.orchestration import RuntimeOrchestrator, run_matrix
from tests.integration.scenarios import (
    register_builtin_scenarios,
    reset_builtin_flag,
)
from tests.integration.utils import fingerprint_signals, signals_match

register_builtin_scenarios()

__all__ = [
    "DEFAULT_DETERMINISM_RUNS",
    "DEFAULT_RENDER_FRAMES",
    "DEFAULT_REPLAY_FRAMES",
    "DEFAULT_SCENARIO_BUDGET_S",
    "DEFAULT_TASK_COUNT",
    "DEFAULT_TRACE_CAPACITY",
    "DEFAULT_WEBSOCKET_EVENTS",
    "DEFAULT_WEBSOCKET_SUBSCRIBERS",
    "CategoryRollup",
    "IntegrationCategory",
    "IntegrationConfig",
    "IntegrationContext",
    "IntegrationMetrics",
    "IntegrationMetricsSnapshot",
    "IntegrationOutcome",
    "IntegrationRegistry",
    "IntegrationReport",
    "IntegrationRunInputs",
    "IntegrationRunner",
    "IntegrationScenarioSpec",
    "IntegrationSeverity",
    "IntegrationSignal",
    "IntegrationSignalKind",
    "IntegrationThresholds",
    "IntegrationTraceEntry",
    "IntegrationTraceKind",
    "IntegrationVerdict",
    "IntegrationViolation",
    "RegisteredScenario",
    "RuntimeOrchestrator",
    "ScenarioCallable",
    "build_integration_report",
    "build_test_context",
    "clear_integration_trace",
    "compute_survivability_score",
    "default_config",
    "default_integration_registry",
    "derive_scenario_seed",
    "evaluate_violations",
    "fingerprint_signals",
    "get_integration_metrics",
    "get_integration_metrics_snapshot",
    "get_integration_trace",
    "integration_trace_capacity",
    "is_integration_trace_enabled",
    "iter_scenarios",
    "lean_config",
    "lean_test_config",
    "record_integration_trace",
    "register_builtin_scenarios",
    "register_scenario",
    "relaxed_config",
    "reset_builtin_flag",
    "reset_default_registry",
    "reset_integration_metrics",
    "run_default_suite",
    "run_default_suite_sync",
    "run_matrix",
    "run_scenario_async",
    "set_integration_trace_enabled",
    "signals_match",
    "verdict_for",
]
