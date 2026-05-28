"""End-to-end smoke tests for every built-in scenario."""

from __future__ import annotations

import pytest

from tests.integration._framework import (
    IntegrationRunInputs,
    IntegrationRunner,
    build_integration_report,
    default_integration_registry,
    lean_config,
)

ALL_BUILTINS = (
    "runtime.task_lifecycle_pipeline",
    "replay.determinism",
    "replay.scrub_storm",
    "websocket.fanout_pipeline",
    "rendering.render_pipeline",
    "resilience.resilience_integration",
    "overload.overload_recovery",
    "stress.stress_integration",
    "topology.topology_pipeline",
    "observability.metrics_consistency",
    "diagnostics.diagnostics_consistency",
)


@pytest.mark.parametrize("name", ALL_BUILTINS)
async def test_each_scenario_runs(name: str) -> None:
    runner = IntegrationRunner(config=lean_config())
    outcomes = await runner.run(IntegrationRunInputs(only=(name,), uvloop_matrix=False))
    assert len(outcomes) == 1, f"scenario {name} did not run"
    assert outcomes[0].verdict in ("passed", "warned"), outcomes[0]


async def test_full_lean_suite_passes() -> None:
    runner = IntegrationRunner(config=lean_config())
    outcomes = await runner.run(IntegrationRunInputs(uvloop_matrix=False))
    expected_count = len(default_integration_registry())
    assert len(outcomes) == expected_count
    report = build_integration_report(outcomes)
    assert report.metrics.scenarios_errored == 0


async def test_full_suite_is_deterministic_across_two_runs() -> None:
    runner_a = IntegrationRunner(config=lean_config())
    runner_b = IntegrationRunner(config=lean_config())
    out_a = await runner_a.run(
        IntegrationRunInputs(
            only=("replay.determinism", "topology.topology_pipeline"),
            uvloop_matrix=False,
        ),
    )
    out_b = await runner_b.run(
        IntegrationRunInputs(
            only=("replay.determinism", "topology.topology_pipeline"),
            uvloop_matrix=False,
        ),
    )
    for a, b in zip(out_a, out_b, strict=True):
        assert a.operations_completed == b.operations_completed
        assert a.render_frames == b.render_frames
        assert a.determinism_diverged == b.determinism_diverged
