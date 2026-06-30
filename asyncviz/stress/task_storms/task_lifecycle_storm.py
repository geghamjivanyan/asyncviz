"""Bounded asyncio-lifecycle churn.

Spawns *real* asyncio tasks in batches, awaits them, and repeats.
Each batch is small (``concurrency`` tasks) so total memory stays
bounded even when ``lifecycle_churn`` is 50k+.
"""

from __future__ import annotations

import asyncio

from asyncviz.stress.failure_injection.failure_registry import (
    StressInjectedFailure,
)
from asyncviz.stress.harness.scenario_context import ScenarioContext


async def run_task_lifecycle_storm(
    context: ScenarioContext,
    *,
    concurrency: int = 64,
) -> None:
    """Spin up + tear down ``config.lifecycle_churn`` tasks in batches."""
    cfg = context.config
    total = cfg.lifecycle_churn
    if concurrency <= 0:
        raise ValueError(f"concurrency must be > 0 (got {concurrency})")
    remaining = total
    batch_index = 0
    while remaining > 0:
        batch_size = min(concurrency, remaining)
        tasks = [
            asyncio.create_task(_synthetic_task(batch_index * concurrency + i))
            for i in range(batch_size)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                context.record_signal("failure", f"lifecycle:{type(result).__name__}")
            else:
                context.record_signal("operation", "task-completed")
        try:
            context.failure_injection.raise_if_triggered(
                "task.lifecycle.batch",
                detail=f"batch-{batch_index}",
            )
        except StressInjectedFailure:
            context.record_signal("failure", f"lifecycle-batch:{batch_index}")
        remaining -= batch_size
        batch_index += 1


async def _synthetic_task(index: int) -> int:
    await asyncio.sleep(0)
    return index
