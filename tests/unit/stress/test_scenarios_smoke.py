"""End-to-end smoke tests for each built-in storm scenario.

Uses the lean configuration so the test stays under a second.
"""

from __future__ import annotations

import pytest

from asyncviz.stress import (
    StressRunInputs,
    StressRunner,
    assert_outcome_clean,
    build_scalability_report,
    default_stress_registry,
    lean_config,
)

ALL_LEAN_SCENARIOS = (
    "synthetic.baseline",
    "task.creation.10k",
    "task.lifecycle.churn",
    "task.cancellation.storm",
    "task.gather.deep",
    "websocket.fanout.flood",
    "websocket.replay.stream",
    "replay.scrub.storm",
    "topology.node.explosion",
    "render.flood",
    "render.overlay.explosion",
    "executor.fanout",
    "queue.saturation",
    "semaphore.contention",
)


@pytest.mark.parametrize("name", ALL_LEAN_SCENARIOS)
async def test_each_scenario_survives_lean_config(name: str) -> None:
    runner = StressRunner(config=lean_config())
    outcomes = await runner.run(StressRunInputs(only=(name,)))
    assert len(outcomes) == 1, f"scenario {name} did not run"
    outcome = outcomes[0]
    assert_outcome_clean(outcome)
    assert outcome.verdict in ("passed", "warned")


async def test_full_lean_suite_passes() -> None:
    runner = StressRunner(config=lean_config())
    outcomes = await runner.run()
    assert len(outcomes) == len(default_stress_registry())
    report = build_scalability_report(outcomes)
    # We accept warned (e.g. when slow_client_ratio knocks a backlog
    # above the lean threshold) but never failed/errored in a smoke run.
    assert report.summary.errored == 0
    rendered = report.render_text()
    assert "AsyncViz scalability report" in rendered


async def test_suite_is_deterministic_across_two_runs() -> None:
    runner1 = StressRunner(config=lean_config())
    runner2 = StressRunner(config=lean_config())
    out1 = await runner1.run(StressRunInputs(only=("synthetic.baseline", "task.creation.10k")))
    out2 = await runner2.run(StressRunInputs(only=("synthetic.baseline", "task.creation.10k")))
    # operation counts must match exactly across runs for replay-safe
    # scenarios.
    for a, b in zip(out1, out2, strict=True):
        assert a.operations_completed == b.operations_completed
        assert a.operations_failed == b.operations_failed
