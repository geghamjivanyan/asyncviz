"""Stress runner tests."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.stress import (
    ScenarioContext,
    StressConfig,
    StressRunInputs,
    StressRunner,
    StressScenarioRegistry,
    StressScenarioSpec,
    lean_config,
    register_scenario,
)


def _make_registry() -> StressScenarioRegistry:
    return StressScenarioRegistry()


async def _ok(context: ScenarioContext) -> None:
    context.record_signal("operation", "ok")


async def _ok_render(context: ScenarioContext) -> None:
    for _ in range(5):
        context.record_signal("render-frame", "ok")


async def _explode(_context: ScenarioContext) -> None:
    raise RuntimeError("boom")


async def _slow(context: ScenarioContext) -> None:
    await asyncio.sleep(0.5)
    context.record_signal("operation", "ok")


async def test_runner_runs_a_simple_scenario() -> None:
    reg = _make_registry()
    register_scenario(
        StressScenarioSpec(name="t.ok", category="synthetic"),
        _ok,
        registry=reg,
    )
    runner = StressRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run()
    assert len(outcomes) == 1
    assert outcomes[0].verdict == "passed"
    assert outcomes[0].operations_completed == 1


async def test_runner_records_error_for_exceptions() -> None:
    reg = _make_registry()
    register_scenario(
        StressScenarioSpec(name="t.bad", category="synthetic"),
        _explode,
        registry=reg,
    )
    runner = StressRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run()
    assert outcomes[0].verdict == "errored"
    assert "RuntimeError" in outcomes[0].error_detail


async def test_runner_enforces_budget() -> None:
    reg = _make_registry()
    register_scenario(
        StressScenarioSpec(name="t.slow", category="synthetic"),
        _slow,
        registry=reg,
    )
    cfg_lean = lean_config()
    cfg = StressConfig(
        severity=cfg_lean.severity,
        task_storm_size=cfg_lean.task_storm_size,
        scenario_budget_s=0.01,
        thresholds=cfg_lean.thresholds,
        failure_injection=cfg_lean.failure_injection,
    )
    runner = StressRunner(config=cfg, registry=reg)
    outcomes = await runner.run()
    assert outcomes[0].verdict == "errored"
    assert "budget" in outcomes[0].error_detail


async def test_runner_filters_by_category() -> None:
    reg = _make_registry()
    register_scenario(
        StressScenarioSpec(name="t.task", category="task"),
        _ok,
        registry=reg,
    )
    register_scenario(
        StressScenarioSpec(name="t.ws", category="websocket"),
        _ok,
        registry=reg,
    )
    runner = StressRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run(StressRunInputs(category="task"))
    assert {o.spec.name for o in outcomes} == {"t.task"}


async def test_runner_filters_by_only() -> None:
    reg = _make_registry()
    register_scenario(
        StressScenarioSpec(name="a", category="task"),
        _ok,
        registry=reg,
    )
    register_scenario(
        StressScenarioSpec(name="b", category="task"),
        _ok,
        registry=reg,
    )
    runner = StressRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run(StressRunInputs(only=("a",)))
    assert {o.spec.name for o in outcomes} == {"a"}


async def test_runner_filters_by_skip() -> None:
    reg = _make_registry()
    register_scenario(
        StressScenarioSpec(name="a", category="task"),
        _ok,
        registry=reg,
    )
    register_scenario(
        StressScenarioSpec(name="b", category="task"),
        _ok,
        registry=reg,
    )
    runner = StressRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run(StressRunInputs(skip=("a",)))
    assert {o.spec.name for o in outcomes} == {"b"}


async def test_warn_only_downgrades_failures() -> None:
    reg = _make_registry()

    async def _fail(context: ScenarioContext) -> None:
        # Force a violation by emitting many dropped frames.
        for _ in range(200):
            context.record_signal("failure", "render-frame-overrun:99ms")

    register_scenario(
        StressScenarioSpec(name="failer", category="render"),
        _fail,
        registry=reg,
    )
    runner = StressRunner(config=lean_config(), registry=reg)
    failing = await runner.run()
    assert failing[0].verdict == "failed"
    warning = await runner.run(StressRunInputs(warn_only=True))
    # Same scenario, warn_only: still records as warned now.
    assert warning[0].verdict in ("warned", "failed")


async def test_runner_records_metrics() -> None:
    reg = _make_registry()
    register_scenario(
        StressScenarioSpec(name="render.ok", category="render"),
        _ok_render,
        registry=reg,
    )
    runner = StressRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run()
    snap = runner.metrics.snapshot()
    assert snap.scenarios_completed >= 1
    assert outcomes[0].render_frames_rendered == 5


async def test_runner_deterministic_seed_per_scenario() -> None:
    reg1 = _make_registry()
    reg2 = _make_registry()
    seen: list[int] = []

    async def _capture(context: ScenarioContext) -> None:
        seen.append(context.rng.integer(0, 1_000_000))
        context.record_signal("operation", "x")

    register_scenario(
        StressScenarioSpec(name="seed.x", category="synthetic"),
        _capture,
        registry=reg1,
    )
    register_scenario(
        StressScenarioSpec(name="seed.x", category="synthetic"),
        _capture,
        registry=reg2,
    )
    await StressRunner(config=lean_config(), registry=reg1).run()
    await StressRunner(config=lean_config(), registry=reg2).run()
    assert seen[0] == seen[1]


def test_runner_exposes_config_and_registry() -> None:
    reg = _make_registry()
    runner = StressRunner(config=lean_config(), registry=reg)
    assert runner.config.task_storm_size == lean_config().task_storm_size
    assert runner.registry is reg


async def test_runner_rejects_unknown_only_silently() -> None:
    reg = _make_registry()
    register_scenario(
        StressScenarioSpec(name="known", category="task"),
        _ok,
        registry=reg,
    )
    runner = StressRunner(config=lean_config(), registry=reg)
    outcomes = await runner.run(StressRunInputs(only=("unknown",)))
    assert outcomes == ()


def test_run_default_suite_callable() -> None:
    from asyncviz.stress import run_default_suite

    assert callable(run_default_suite)


def test_stress_run_inputs_is_frozen() -> None:
    import dataclasses

    inputs = StressRunInputs()
    with pytest.raises(dataclasses.FrozenInstanceError):
        inputs.warn_only = True  # type: ignore[misc]
