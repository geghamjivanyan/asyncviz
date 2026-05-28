"""IntegrationRunner tests."""

from __future__ import annotations

import asyncio

import pytest

from tests.integration._framework import (
    IntegrationRegistry,
    IntegrationRunInputs,
    IntegrationRunner,
    IntegrationScenarioSpec,
    lean_config,
    register_scenario,
)


async def _ok(context) -> None:
    context.record("operation", "ok")


async def _flaky(context) -> None:
    target = context.rng.integer(0, 9)
    context.record("operation", f"step:{target}")


async def _explode(_context) -> None:
    raise RuntimeError("boom")


async def _slow(_context) -> None:
    await asyncio.sleep(5)


def _registry() -> IntegrationRegistry:
    return IntegrationRegistry()


async def test_runner_runs_simple_scenario() -> None:
    reg = _registry()
    register_scenario(
        IntegrationScenarioSpec(name="x.ok", category="runtime"),
        _ok,
        registry=reg,
    )
    runner = IntegrationRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run()
    assert len(outcomes) == 1
    assert outcomes[0].verdict == "passed"
    assert outcomes[0].operations_completed == 1


async def test_runner_records_errors() -> None:
    reg = _registry()
    register_scenario(
        IntegrationScenarioSpec(name="x.bad", category="runtime"),
        _explode,
        registry=reg,
    )
    runner = IntegrationRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run()
    assert outcomes[0].verdict == "errored"


async def test_runner_enforces_budget() -> None:
    reg = _registry()
    register_scenario(
        IntegrationScenarioSpec(name="x.slow", category="runtime"),
        _slow,
        registry=reg,
    )
    cfg = lean_config()
    cfg = type(cfg)(
        severity=cfg.severity,
        task_count=cfg.task_count,
        replay_frames=cfg.replay_frames,
        websocket_subscribers=cfg.websocket_subscribers,
        websocket_events=cfg.websocket_events,
        render_frames=cfg.render_frames,
        render_invalidations=cfg.render_invalidations,
        scenario_budget_s=0.05,
        determinism_runs=1,
        seed=cfg.seed,
        trace_capacity=cfg.trace_capacity,
        enable_tracing=cfg.enable_tracing,
        enable_uvloop_matrix=False,
        thresholds=cfg.thresholds,
    )
    runner = IntegrationRunner(config=cfg, registry=reg)
    outcomes = await runner.run()
    assert outcomes[0].verdict == "errored"
    assert "budget" in outcomes[0].error_detail


async def test_runner_determinism_runs_match() -> None:
    reg = _registry()
    register_scenario(
        IntegrationScenarioSpec(name="x.flaky", category="runtime"),
        _flaky,
        registry=reg,
    )
    runner = IntegrationRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run(IntegrationRunInputs(determinism=True))
    assert outcomes[0].determinism_runs >= 2
    assert outcomes[0].determinism_diverged is False
    assert outcomes[0].verdict == "passed"


async def test_runner_filters_by_only() -> None:
    reg = _registry()
    register_scenario(
        IntegrationScenarioSpec(name="a", category="runtime"),
        _ok,
        registry=reg,
    )
    register_scenario(
        IntegrationScenarioSpec(name="b", category="runtime"),
        _ok,
        registry=reg,
    )
    runner = IntegrationRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run(IntegrationRunInputs(only=("a",)))
    assert {o.spec.name for o in outcomes} == {"a"}


async def test_runner_filters_by_skip() -> None:
    reg = _registry()
    register_scenario(
        IntegrationScenarioSpec(name="a", category="runtime"),
        _ok,
        registry=reg,
    )
    register_scenario(
        IntegrationScenarioSpec(name="b", category="runtime"),
        _ok,
        registry=reg,
    )
    runner = IntegrationRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run(IntegrationRunInputs(skip=("a",)))
    assert {o.spec.name for o in outcomes} == {"b"}


def test_run_default_suite_sync_callable() -> None:
    from tests.integration._framework import run_default_suite_sync

    assert callable(run_default_suite_sync)


def test_run_inputs_immutable() -> None:
    import dataclasses

    inputs = IntegrationRunInputs()
    with pytest.raises(dataclasses.FrozenInstanceError):
        inputs.warn_only = True  # type: ignore[misc]
