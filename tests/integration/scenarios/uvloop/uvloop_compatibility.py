"""uvloop compatibility integration scenario.

Records the active loop kind + the clock-drift sample, then runs a
small task batch so the matrix runner can compare counts across
loops.
"""

from __future__ import annotations

import asyncio

from asyncviz.runtime.compat import (  # type: ignore[import-not-found]
    LoopCompatibilityManager,
)
from tests.integration.harness.scenario_context import IntegrationContext


async def run_uvloop_compatibility(context: IntegrationContext) -> None:
    mgr = LoopCompatibilityManager()
    caps = mgr.attach()
    context.record("operation", f"loop={caps.kind.value}")

    bridge = mgr.clock_bridge()
    bridge.sample()
    await asyncio.sleep(0.001)
    bridge.sample()

    # Spawn a small batch so the task bridge counter ticks.
    async def _noop() -> None:
        await asyncio.sleep(0)

    await asyncio.gather(*(_noop() for _ in range(16)))
    task_stats = mgr.task_bridge().stats()
    context.record(
        "custom",
        f"tasks_completed={task_stats.tasks_completed}",
        value=float(task_stats.tasks_completed),
    )
    drift = bridge.report()
    context.record(
        "custom",
        f"drift_ns={drift.last_drift_ns}",
        value=float(drift.last_drift_ns),
    )
    mgr.detach()
