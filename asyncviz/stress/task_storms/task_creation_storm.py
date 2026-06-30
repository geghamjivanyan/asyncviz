"""Massive task-creation + lifecycle churn.

The storm produces ``size`` task descriptors via the synthetic
workload generator and *simulates* their lifecycle by recording
signals against the runner. The simulation deliberately doesn't
spawn real asyncio tasks — that would conflate the runtime
instrumentation overhead with the scalability test. Scenarios that
need real tasks live in :mod:`task_lifecycle_storm`.
"""

from __future__ import annotations

from asyncviz.stress.failure_injection.failure_registry import (
    StressInjectedFailure,
)
from asyncviz.stress.harness.scenario_context import ScenarioContext
from asyncviz.stress.workload_generators.task_workload import (
    generate_task_storm,
)


async def run_task_creation_storm(context: ScenarioContext) -> None:
    """Drive ``config.task_storm_size`` synthetic task lifecycles."""
    cfg = context.config
    iterator = generate_task_storm(
        size=cfg.task_storm_size,
        seed=context.rng.seed,
        dependency_depth=cfg.dependency_depth,
        cancel_ratio=0.0,
        failure_ratio=0.0,
    )
    for descriptor in iterator:
        try:
            context.failure_injection.raise_if_triggered(
                "task.create",
                detail=descriptor.task_id,
            )
        except StressInjectedFailure:
            context.record_signal("failure", f"task.create:{descriptor.task_id}")
            continue
        context.record_signal("operation", f"task-created:{descriptor.task_id}")
