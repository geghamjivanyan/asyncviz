"""Stress registry tests."""

from __future__ import annotations

import pytest

from asyncviz.stress import (
    StressScenarioRegistry,
    StressScenarioSpec,
    iter_categories,
    register_scenario,
    stress_scenario,
)


async def _noop(_context) -> None:  # pragma: no cover - registered then unused
    return None


def test_register_and_get() -> None:
    reg = StressScenarioRegistry()
    spec = StressScenarioSpec(name="x", category="task")
    register_scenario(spec, _noop, registry=reg)
    entry = reg.get("x")
    assert entry is not None
    assert entry.spec.name == "x"


def test_duplicate_registration_raises() -> None:
    reg = StressScenarioRegistry()
    spec = StressScenarioSpec(name="x", category="task")
    register_scenario(spec, _noop, registry=reg)
    with pytest.raises(ValueError):
        register_scenario(spec, _noop, registry=reg)


def test_filter_by_category() -> None:
    reg = StressScenarioRegistry()
    register_scenario(StressScenarioSpec(name="a", category="task"), _noop, registry=reg)
    register_scenario(
        StressScenarioSpec(name="b", category="websocket"),
        _noop,
        registry=reg,
    )
    task_entries = reg.by_category("task")
    assert len(task_entries) == 1
    assert task_entries[0].spec.name == "a"


def test_clear() -> None:
    reg = StressScenarioRegistry()
    register_scenario(StressScenarioSpec(name="a", category="task"), _noop, registry=reg)
    reg.clear()
    assert len(reg) == 0


def test_contains_and_len() -> None:
    reg = StressScenarioRegistry()
    register_scenario(StressScenarioSpec(name="a", category="task"), _noop, registry=reg)
    assert "a" in reg
    assert len(reg) == 1


def test_decorator_registers() -> None:
    reg = StressScenarioRegistry()

    @stress_scenario(name="dec.x", category="synthetic", registry=reg)
    async def _scenario(_context):
        return None

    assert "dec.x" in reg
    # Returned function is unchanged.
    assert callable(_scenario)


def test_iter_categories_stable() -> None:
    reg = StressScenarioRegistry()
    register_scenario(StressScenarioSpec(name="a", category="task"), _noop, registry=reg)
    register_scenario(
        StressScenarioSpec(name="b", category="websocket"),
        _noop,
        registry=reg,
    )
    register_scenario(StressScenarioSpec(name="c", category="task"), _noop, registry=reg)
    cats = list(iter_categories(reg))
    assert cats == ["task", "websocket"]
