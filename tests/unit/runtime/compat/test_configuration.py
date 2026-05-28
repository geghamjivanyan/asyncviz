"""Compat configuration tests."""

from __future__ import annotations

import dataclasses

import pytest

from asyncviz.runtime.compat import (
    LoopCompatConfig,
    default_config,
    prefer_uvloop_config,
    strict_asyncio_config,
)


def test_default_config_is_passive() -> None:
    cfg = default_config()
    assert cfg.preference == "auto"
    assert cfg.install_on_attach is False


def test_prefer_uvloop_config_requests_install() -> None:
    cfg = prefer_uvloop_config()
    assert cfg.preference == "uvloop"
    assert cfg.install_on_attach is True
    assert cfg.fallback_on_install_failure is True


def test_strict_asyncio_config_disallows_install() -> None:
    cfg = strict_asyncio_config()
    assert cfg.preference == "asyncio"
    assert cfg.fallback_on_install_failure is False


def test_config_is_frozen() -> None:
    cfg = LoopCompatConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.preference = "uvloop"  # type: ignore[misc]


def test_drift_tolerance_default_is_reasonable() -> None:
    cfg = default_config()
    assert cfg.clock_drift_tolerance_ns > 0
    assert cfg.clock_drift_tolerance_ns <= 10 ** 9  # never more than 1s
