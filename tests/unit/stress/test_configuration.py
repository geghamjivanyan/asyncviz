"""Stress configuration tests."""

from __future__ import annotations

from asyncviz.stress import (
    StressConfig,
    default_config,
    lean_config,
    relaxed_config,
)


def test_default_config_has_documented_defaults() -> None:
    cfg = default_config()
    assert cfg.task_storm_size == 10_000
    assert cfg.severity == "moderate"
    assert cfg.scenario_budget_s > 0
    assert 0.0 <= cfg.slow_client_ratio <= 1.0


def test_lean_config_is_smaller() -> None:
    cfg = lean_config()
    base = default_config()
    assert cfg.task_storm_size < base.task_storm_size
    assert cfg.websocket_subscribers < base.websocket_subscribers
    assert cfg.scenario_budget_s <= base.scenario_budget_s


def test_relaxed_config_is_larger() -> None:
    cfg = relaxed_config()
    base = default_config()
    assert cfg.task_storm_size > base.task_storm_size
    assert cfg.websocket_subscribers > base.websocket_subscribers


def test_config_is_immutable() -> None:
    cfg = default_config()
    import dataclasses

    assert dataclasses.is_dataclass(cfg)
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.task_storm_size = 1  # type: ignore[misc]


def test_thresholds_can_be_disabled_per_field() -> None:
    cfg = StressConfig.__dataclass_fields__["thresholds"].default_factory()
    assert cfg.max_dropped_frames is not None
    assert cfg.min_fps is not None
