"""Failure-injection registry tests."""

from __future__ import annotations

import pytest

from asyncviz.stress import FailureInjectionConfig, FailureInjectionRegistry
from asyncviz.stress.failure_injection.failure_registry import (
    StressInjectedFailure,
)


def test_registry_disabled_never_fires() -> None:
    reg = FailureInjectionRegistry(FailureInjectionConfig(enabled=False))
    for _ in range(100):
        assert not reg.maybe_inject("websocket.disconnect")


def test_registry_enabled_fires_at_documented_rate() -> None:
    cfg = FailureInjectionConfig(enabled=True, injection_rate=0.5, seed=1)
    reg = FailureInjectionRegistry(cfg)
    triggers = sum(reg.maybe_inject("websocket.disconnect") for _ in range(1000))
    # Expect ~500 ± noise — 200-800 catches catastrophic regressions
    # without flaking.
    assert 200 < triggers < 800


def test_registry_is_deterministic_given_seed() -> None:
    cfg = FailureInjectionConfig(enabled=True, injection_rate=0.3, seed=42)
    a = FailureInjectionRegistry(cfg)
    b = FailureInjectionRegistry(cfg)
    a_results = [a.maybe_inject("reducer.exception") for _ in range(100)]
    b_results = [b.maybe_inject("reducer.exception") for _ in range(100)]
    assert a_results == b_results


def test_registry_independent_streams_per_site() -> None:
    cfg = FailureInjectionConfig(enabled=True, injection_rate=0.5, seed=42)
    reg = FailureInjectionRegistry(cfg)
    a_results = [reg.maybe_inject("siteA") for _ in range(100)]
    b_results = [reg.maybe_inject("siteB") for _ in range(100)]
    # Both should fire some, but the streams must differ.
    assert a_results != b_results


def test_registry_respects_per_site_toggle() -> None:
    cfg = FailureInjectionConfig(
        enabled=True,
        injection_rate=1.0,
        seed=1,
        websocket_disconnects=False,
        reducer_exceptions=True,
    )
    reg = FailureInjectionRegistry(cfg)
    assert not reg.maybe_inject("websocket.disconnect")
    assert reg.maybe_inject("reducer.exception")


def test_raise_if_triggered_raises_on_fire() -> None:
    cfg = FailureInjectionConfig(enabled=True, injection_rate=1.0, seed=1)
    reg = FailureInjectionRegistry(cfg)
    with pytest.raises(StressInjectedFailure):
        reg.raise_if_triggered("queue.saturation")


def test_raise_if_triggered_silent_when_not_fired() -> None:
    cfg = FailureInjectionConfig(enabled=False)
    reg = FailureInjectionRegistry(cfg)
    reg.raise_if_triggered("queue.saturation")  # must not raise


def test_registry_stats_track_invocations_and_triggers() -> None:
    cfg = FailureInjectionConfig(enabled=True, injection_rate=0.5, seed=1)
    reg = FailureInjectionRegistry(cfg)
    for _ in range(50):
        reg.maybe_inject("site")
    stats = reg.stats()
    assert len(stats) == 1
    assert stats[0].invocations == 50
    assert 0 < stats[0].triggers <= 50


def test_registry_reset() -> None:
    cfg = FailureInjectionConfig(enabled=True, injection_rate=1.0, seed=1)
    reg = FailureInjectionRegistry(cfg)
    reg.maybe_inject("site")
    reg.reset()
    assert reg.stats() == ()
