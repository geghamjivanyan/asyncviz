"""Integration-config tests."""

from __future__ import annotations

import dataclasses

import pytest

from tests.integration._framework import (
    IntegrationConfig,
    default_config,
    lean_config,
    relaxed_config,
)


def test_default_config_reasonable() -> None:
    cfg = default_config()
    assert cfg.task_count > 0
    assert cfg.replay_frames > 0
    assert cfg.scenario_budget_s > 0
    assert cfg.thresholds.require_replay_determinism is True


def test_lean_config_is_smaller() -> None:
    base = default_config()
    cfg = lean_config()
    assert cfg.task_count < base.task_count
    assert cfg.replay_frames < base.replay_frames
    assert cfg.scenario_budget_s <= base.scenario_budget_s


def test_relaxed_config_is_larger() -> None:
    base = default_config()
    cfg = relaxed_config()
    assert cfg.task_count > base.task_count
    assert cfg.replay_frames > base.replay_frames
    assert cfg.enable_uvloop_matrix is True


def test_config_is_frozen() -> None:
    cfg = IntegrationConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.task_count = 1  # type: ignore[misc]
