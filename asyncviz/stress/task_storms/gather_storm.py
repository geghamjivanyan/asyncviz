"""Nested-gather storm.

Builds a tree of ``asyncio.gather`` calls ``dependency_depth`` levels
deep with ``gather_fanout`` siblings per node. Used to validate the
gather instrumentation is bounded under deep nesting.
"""

from __future__ import annotations

import asyncio

from asyncviz.stress.harness.scenario_context import ScenarioContext


async def run_gather_storm(context: ScenarioContext) -> None:
    cfg = context.config
    if cfg.dependency_depth < 1:
        raise ValueError("dependency_depth must be >= 1")
    if cfg.gather_fanout < 1:
        raise ValueError("gather_fanout must be >= 1")
    await _gather_layer(context, depth=cfg.dependency_depth)


async def _gather_layer(context: ScenarioContext, *, depth: int) -> int:
    if depth <= 1:
        context.record_signal("operation", "leaf")
        return 1
    fanout = context.config.gather_fanout
    coroutines = [
        _gather_layer(context, depth=depth - 1) for _ in range(fanout)
    ]
    results = await asyncio.gather(*coroutines)
    context.record_signal("operation", f"gather:depth={depth}")
    return sum(results)
