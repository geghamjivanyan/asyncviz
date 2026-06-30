"""Cancellation-storm scenario.

Spawns batches of long-sleep tasks and cancels them en masse.
Verifies cancellation propagation is bounded + cleanup completes.
"""

from __future__ import annotations

import asyncio

from asyncviz.stress.harness.scenario_context import ScenarioContext


async def run_cancellation_storm(
    context: ScenarioContext,
    *,
    concurrency: int = 64,
) -> None:
    cfg = context.config
    if concurrency <= 0:
        raise ValueError(f"concurrency must be > 0 (got {concurrency})")
    remaining = cfg.cancel_storm_size
    batch_index = 0
    while remaining > 0:
        batch_size = min(concurrency, remaining)
        tasks = [asyncio.create_task(_long_sleeper()) for _ in range(batch_size)]
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, asyncio.CancelledError):
                context.record_signal("operation", "task-cancelled")
            else:
                context.record_signal("failure", "task-cancel-unexpected")
        remaining -= batch_size
        batch_index += 1


async def _long_sleeper() -> None:
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        raise
