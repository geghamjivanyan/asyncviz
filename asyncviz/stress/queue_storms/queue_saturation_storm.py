"""Queue-saturation storm.

Drives a bounded :class:`asyncio.Queue` past its capacity and tracks
how many items end up dropped + how the producer responds. Used to
validate that the production code on top of the queue does not
deadlock when ``put`` blocks repeatedly.
"""

from __future__ import annotations

import asyncio

from asyncviz.stress.failure_injection.failure_registry import (
    StressInjectedFailure,
)
from asyncviz.stress.harness.scenario_context import ScenarioContext


async def run_queue_saturation_storm(context: ScenarioContext) -> None:
    cfg = context.config
    capacity = max(8, cfg.queue_depth // 16)
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=capacity)
    drops = 0
    for index in range(cfg.queue_depth):
        try:
            context.failure_injection.raise_if_triggered(
                "queue.saturation",
                detail=str(index),
            )
        except StressInjectedFailure:
            drops += 1
            context.record_signal("failure", "queue-injected-drop")
            continue
        try:
            queue.put_nowait(index)
            context.record_signal("operation", "queue-put")
        except asyncio.QueueFull:
            drops += 1
            # QueueFull is the *expected* outcome of overflowing a
            # bounded queue. The drop counter belongs to the custom-
            # metric stream rather than the failure stream so it
            # doesn't tank the survivability score.
            context.record_signal("custom", "queue-full")
            # Drain one item so the storm can continue.
            try:
                queue.get_nowait()
                queue.task_done()
            except asyncio.QueueEmpty:
                pass
    while not queue.empty():
        queue.get_nowait()
        queue.task_done()
    context.record_signal("custom", f"queue-drops={drops}", float(drops))
