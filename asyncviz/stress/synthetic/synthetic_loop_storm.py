"""Synthetic baseline loop storm.

A minimal scenario that records operations without doing real work
— used to measure stress-runner overhead (warmup, signal-recording
cost, observability lock contention) in isolation from the storms
themselves.
"""

from __future__ import annotations

from asyncviz.stress.harness.scenario_context import ScenarioContext


async def run_synthetic_loop_storm(
    context: ScenarioContext,
    *,
    iterations: int = 1_000,
) -> None:
    if iterations < 0:
        raise ValueError(f"iterations must be >= 0 (got {iterations})")
    for index in range(iterations):
        context.record_signal("operation", f"baseline:{index}")
