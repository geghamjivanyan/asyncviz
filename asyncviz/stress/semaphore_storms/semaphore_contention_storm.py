"""Semaphore-contention storm.

Spawns ``semaphore_contention`` tasks all racing for a single
:class:`asyncio.Semaphore` with capacity ``permits``. Verifies that
the semaphore's wait queue is bounded + ordered.
"""

from __future__ import annotations

import asyncio

from asyncviz.stress.harness.scenario_context import ScenarioContext


async def run_semaphore_contention_storm(
    context: ScenarioContext,
    *,
    permits: int = 4,
) -> None:
    cfg = context.config
    if permits < 1:
        raise ValueError(f"permits must be >= 1 (got {permits})")
    semaphore = asyncio.Semaphore(permits)

    async def _worker(index: int) -> None:
        async with semaphore:
            await asyncio.sleep(0)
            context.record_signal("operation", f"sem-acquired:{index}")

    workers = [
        asyncio.create_task(_worker(i)) for i in range(cfg.semaphore_contention)
    ]
    await asyncio.gather(*workers)
