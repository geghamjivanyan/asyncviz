"""Built-in scenario registrations.

Imported by :mod:`asyncviz.stress.__init__` so the default registry
is populated as soon as the package is imported. Tests that want a
clean slate can call :func:`reset_default_registry` then re-register
or build their own :class:`StressScenarioRegistry`.
"""

from __future__ import annotations

from asyncviz.stress.executor_storms.executor_fanout_storm import (
    run_executor_fanout_storm,
)
from asyncviz.stress.models.stress_scenario import StressScenarioSpec
from asyncviz.stress.queue_storms.queue_saturation_storm import (
    run_queue_saturation_storm,
)
from asyncviz.stress.rendering_storms.overlay_explosion_storm import (
    run_overlay_explosion_storm,
)
from asyncviz.stress.rendering_storms.render_flood_storm import (
    run_render_flood_storm,
)
from asyncviz.stress.replay_storms.replay_scrub_storm import (
    run_replay_scrub_storm,
)
from asyncviz.stress.semaphore_storms.semaphore_contention_storm import (
    run_semaphore_contention_storm,
)
from asyncviz.stress.stress_registry import (
    StressScenarioRegistry,
    default_stress_registry,
    register_scenario,
)
from asyncviz.stress.synthetic.synthetic_loop_storm import (
    run_synthetic_loop_storm,
)
from asyncviz.stress.task_storms.cancellation_storm import (
    run_cancellation_storm,
)
from asyncviz.stress.task_storms.gather_storm import run_gather_storm
from asyncviz.stress.task_storms.task_creation_storm import (
    run_task_creation_storm,
)
from asyncviz.stress.task_storms.task_lifecycle_storm import (
    run_task_lifecycle_storm,
)
from asyncviz.stress.topology_storms.topology_explosion_storm import (
    run_topology_explosion_storm,
)
from asyncviz.stress.websocket_floods.replay_stream_flood import (
    run_replay_stream_flood,
)
from asyncviz.stress.websocket_floods.websocket_flood import run_websocket_flood

_BUILTINS_REGISTERED = False


def register_builtin_scenarios(
    registry: StressScenarioRegistry | None = None,
) -> None:
    """Register the built-in scenario suite.

    Safe to call repeatedly: subsequent calls are no-ops because the
    registry rejects duplicate names. Tests that want a fully clean
    registry call :func:`reset_default_registry` first.
    """
    global _BUILTINS_REGISTERED
    target = registry if registry is not None else default_stress_registry()
    if registry is None and _BUILTINS_REGISTERED:
        return
    entries = (
        (
            StressScenarioSpec(
                name="task.creation.10k",
                category="task",
                severity="heavy",
                description="Drive 10k synthetic task lifecycles.",
                replay_safe=True,
                failure_injection=True,
            ),
            run_task_creation_storm,
        ),
        (
            StressScenarioSpec(
                name="task.lifecycle.churn",
                category="task",
                severity="heavy",
                description="Spawn + tear down lifecycle_churn tasks.",
                replay_safe=False,
                failure_injection=True,
            ),
            run_task_lifecycle_storm,
        ),
        (
            StressScenarioSpec(
                name="task.cancellation.storm",
                category="task",
                severity="heavy",
                description="Mass-cancel batches of sleeping tasks.",
                replay_safe=False,
                failure_injection=False,
            ),
            run_cancellation_storm,
        ),
        (
            StressScenarioSpec(
                name="task.gather.deep",
                category="task",
                severity="moderate",
                description="Nested gather tree of depth+fanout.",
                replay_safe=False,
                failure_injection=False,
            ),
            run_gather_storm,
        ),
        (
            StressScenarioSpec(
                name="websocket.fanout.flood",
                category="websocket",
                severity="heavy",
                description="Fanout to thousands of subscribers.",
                replay_safe=True,
                failure_injection=True,
            ),
            run_websocket_flood,
        ),
        (
            StressScenarioSpec(
                name="websocket.replay.stream",
                category="websocket",
                severity="moderate",
                description="High-rate replay frame stream.",
                replay_safe=True,
                failure_injection=False,
            ),
            run_replay_stream_flood,
        ),
        (
            StressScenarioSpec(
                name="replay.scrub.storm",
                category="replay",
                severity="moderate",
                description="Rapid scrub-hop bookkeeping.",
                replay_safe=True,
                failure_injection=False,
            ),
            run_replay_scrub_storm,
        ),
        (
            StressScenarioSpec(
                name="topology.node.explosion",
                category="topology",
                severity="heavy",
                description="DAG growth + bounded view validation.",
                replay_safe=True,
                failure_injection=False,
            ),
            run_topology_explosion_storm,
        ),
        (
            StressScenarioSpec(
                name="render.flood",
                category="render",
                severity="heavy",
                description="Frame + region invalidation flood.",
                replay_safe=True,
                failure_injection=False,
            ),
            run_render_flood_storm,
        ),
        (
            StressScenarioSpec(
                name="render.overlay.explosion",
                category="render",
                severity="moderate",
                description="Cursor / selection overlay coalescing.",
                replay_safe=True,
                failure_injection=False,
            ),
            run_overlay_explosion_storm,
        ),
        (
            StressScenarioSpec(
                name="executor.fanout",
                category="executor",
                severity="moderate",
                description="call_soon fanout to the event loop.",
                replay_safe=False,
                failure_injection=False,
            ),
            run_executor_fanout_storm,
        ),
        (
            StressScenarioSpec(
                name="queue.saturation",
                category="queue",
                severity="heavy",
                description="Bounded queue overflow handling.",
                replay_safe=True,
                failure_injection=True,
            ),
            run_queue_saturation_storm,
        ),
        (
            StressScenarioSpec(
                name="semaphore.contention",
                category="semaphore",
                severity="moderate",
                description="Many tasks racing for a single semaphore.",
                replay_safe=False,
                failure_injection=False,
            ),
            run_semaphore_contention_storm,
        ),
        (
            StressScenarioSpec(
                name="synthetic.baseline",
                category="synthetic",
                severity="light",
                description="Baseline runner overhead measurement.",
                replay_safe=True,
                failure_injection=False,
            ),
            run_synthetic_loop_storm,
        ),
    )
    for spec, runner in entries:
        if spec.name in target:
            continue
        register_scenario(spec, runner, registry=target)
    if registry is None:
        _BUILTINS_REGISTERED = True


def reset_builtin_flag() -> None:
    """Test-only: forget that built-ins were registered."""
    global _BUILTINS_REGISTERED
    _BUILTINS_REGISTERED = False
