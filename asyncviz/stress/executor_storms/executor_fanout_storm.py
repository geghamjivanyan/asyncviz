"""Executor-fanout storm.

Floods an ``asyncio`` event loop with synchronous callbacks scheduled
via :func:`loop.call_soon` and gathers them. Bounded — each callback
is trivial; the storm measures whether the loop's task-creation +
callback queue scale to ``executor_fanout`` items per batch.
"""

from __future__ import annotations

import asyncio

from asyncviz.stress.harness.scenario_context import ScenarioContext


async def run_executor_fanout_storm(context: ScenarioContext) -> None:
    cfg = context.config
    fanout = cfg.executor_fanout
    if fanout < 1:
        raise ValueError(f"executor_fanout must be >= 1 (got {fanout})")
    futures = [asyncio.get_running_loop().create_future() for _ in range(fanout)]
    for future in futures:
        asyncio.get_running_loop().call_soon(_resolve, future)
    await asyncio.gather(*futures)
    for _ in futures:
        context.record_signal("operation", "executor-callback")


def _resolve(future: asyncio.Future[int]) -> None:
    if not future.done():
        future.set_result(0)
