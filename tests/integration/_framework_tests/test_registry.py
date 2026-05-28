"""Integration registry tests."""

from __future__ import annotations

import pytest

from tests.integration._framework import (
    IntegrationRegistry,
    IntegrationScenarioSpec,
    register_scenario,
)


async def _noop(_ctx) -> None:  # pragma: no cover — registration target
    return None


def test_register_and_get() -> None:
    reg = IntegrationRegistry()
    spec = IntegrationScenarioSpec(name="x", category="runtime")
    register_scenario(spec, _noop, registry=reg)
    entry = reg.get("x")
    assert entry is not None
    assert entry.spec.name == "x"


def test_duplicate_raises() -> None:
    reg = IntegrationRegistry()
    spec = IntegrationScenarioSpec(name="x", category="runtime")
    register_scenario(spec, _noop, registry=reg)
    with pytest.raises(ValueError):
        register_scenario(spec, _noop, registry=reg)


def test_filter_by_category() -> None:
    reg = IntegrationRegistry()
    register_scenario(
        IntegrationScenarioSpec(name="a", category="runtime"),
        _noop,
        registry=reg,
    )
    register_scenario(
        IntegrationScenarioSpec(name="b", category="replay"),
        _noop,
        registry=reg,
    )
    runtime = reg.by_category("runtime")
    assert len(runtime) == 1 and runtime[0].spec.name == "a"


def test_clear() -> None:
    reg = IntegrationRegistry()
    register_scenario(
        IntegrationScenarioSpec(name="a", category="runtime"),
        _noop,
        registry=reg,
    )
    reg.clear()
    assert len(reg) == 0
