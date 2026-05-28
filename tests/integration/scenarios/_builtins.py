"""Register the built-in integration scenarios with the default registry."""

from __future__ import annotations

from tests.integration.integration_models import IntegrationScenarioSpec
from tests.integration.integration_registry import (
    IntegrationRegistry,
    default_integration_registry,
    register_scenario,
)
from tests.integration.scenarios.diagnostics_validation.diagnostics_consistency import (
    run_diagnostics_consistency,
)
from tests.integration.scenarios.observability_validation.metrics_consistency import (
    run_metrics_consistency,
)
from tests.integration.scenarios.overload.overload_recovery import (
    run_overload_recovery,
)
from tests.integration.scenarios.rendering.render_pipeline import (
    run_render_pipeline,
)
from tests.integration.scenarios.replay.replay_determinism import (
    run_replay_determinism,
)
from tests.integration.scenarios.replay.replay_scrub import (
    run_replay_scrub_storm,
)
from tests.integration.scenarios.resilience.resilience_integration import (
    run_resilience_integration,
)
from tests.integration.scenarios.runtime.task_lifecycle_pipeline import (
    run_task_lifecycle_pipeline,
)
from tests.integration.scenarios.stress.stress_integration import (
    run_stress_integration,
)
from tests.integration.scenarios.topology.topology_pipeline import (
    run_topology_pipeline,
)
from tests.integration.scenarios.uvloop.uvloop_compatibility import (
    run_uvloop_compatibility,
)
from tests.integration.scenarios.websocket.fanout_pipeline import (
    run_websocket_fanout_pipeline,
)

_BUILTINS_REGISTERED = False


def register_builtin_scenarios(
    registry: IntegrationRegistry | None = None,
) -> None:
    global _BUILTINS_REGISTERED
    target = registry if registry is not None else default_integration_registry()
    if registry is None and _BUILTINS_REGISTERED:
        return
    entries = (
        (
            IntegrationScenarioSpec(
                name="runtime.task_lifecycle_pipeline",
                category="runtime",
                description="Tasks → websocket → replay → render end-to-end.",
            ),
            run_task_lifecycle_pipeline,
        ),
        (
            IntegrationScenarioSpec(
                name="replay.determinism",
                category="replay",
                description="Two replay runs with identical seeds match.",
            ),
            run_replay_determinism,
        ),
        (
            IntegrationScenarioSpec(
                name="replay.scrub_storm",
                category="replay",
                description="High-rate scrub bookkeeping determinism.",
            ),
            run_replay_scrub_storm,
        ),
        (
            IntegrationScenarioSpec(
                name="websocket.fanout_pipeline",
                category="websocket",
                description="Fanout to many subscribers with backpressure.",
            ),
            run_websocket_fanout_pipeline,
        ),
        (
            IntegrationScenarioSpec(
                name="rendering.render_pipeline",
                category="rendering",
                description="Render tick stream + drop bookkeeping.",
            ),
            run_render_pipeline,
        ),
        (
            IntegrationScenarioSpec(
                name="resilience.resilience_integration",
                category="resilience",
                description="Replay/reducer/recorder failure cascade.",
                replay_safe=False,
            ),
            run_resilience_integration,
        ),
        (
            IntegrationScenarioSpec(
                name="overload.overload_recovery",
                category="overload",
                description="Degraded → recovery cycle.",
                replay_safe=False,
            ),
            run_overload_recovery,
        ),
        (
            IntegrationScenarioSpec(
                name="uvloop.compatibility",
                category="uvloop",
                description="Loop-compat manager attach + drift sample.",
                replay_safe=False,
            ),
            run_uvloop_compatibility,
        ),
        (
            IntegrationScenarioSpec(
                name="stress.stress_integration",
                category="stress",
                description="Stress runner exercised inside integration suite.",
                replay_safe=False,
            ),
            run_stress_integration,
        ),
        (
            IntegrationScenarioSpec(
                name="topology.topology_pipeline",
                category="topology",
                description="Synthetic topology growth.",
            ),
            run_topology_pipeline,
        ),
        (
            IntegrationScenarioSpec(
                name="observability.metrics_consistency",
                category="observability",
                description="Cross-layer metrics agreement.",
                replay_safe=False,
            ),
            run_metrics_consistency,
        ),
        (
            IntegrationScenarioSpec(
                name="diagnostics.diagnostics_consistency",
                category="diagnostics",
                description="Cross-layer diagnostics structure check.",
                replay_safe=False,
            ),
            run_diagnostics_consistency,
        ),
    )
    for spec, runner in entries:
        if spec.name in target:
            continue
        register_scenario(spec, runner, registry=target)
    if registry is None:
        _BUILTINS_REGISTERED = True


def reset_builtin_flag() -> None:
    global _BUILTINS_REGISTERED
    _BUILTINS_REGISTERED = False
