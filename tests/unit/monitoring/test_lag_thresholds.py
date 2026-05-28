from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.event_loop.lag_thresholds import (
    LagSeverity,
    LagThresholds,
)


def test_default_thresholds_classify_correctly() -> None:
    t = LagThresholds()  # 50ms / 250ms / 1s defaults
    assert t.evaluate(0).severity is LagSeverity.NORMAL
    assert t.evaluate(40_000_000).severity is LagSeverity.NORMAL  # 40ms
    assert t.evaluate(50_000_000).severity is LagSeverity.WARNING  # exact threshold
    assert t.evaluate(100_000_000).severity is LagSeverity.WARNING
    assert t.evaluate(250_000_000).severity is LagSeverity.CRITICAL
    assert t.evaluate(500_000_000).severity is LagSeverity.CRITICAL
    assert t.evaluate(1_000_000_000).severity is LagSeverity.FREEZE
    assert t.evaluate(2_000_000_000).severity is LagSeverity.FREEZE


def test_threshold_evaluation_carries_breached_flag() -> None:
    t = LagThresholds(warning_seconds=0.01, critical_seconds=0.1, freeze_seconds=1.0)
    assert t.evaluate(0).breached is False
    assert t.evaluate(10_000_000).breached is True


def test_disabled_tier_never_trips() -> None:
    t = LagThresholds(warning_seconds=None, critical_seconds=0.1, freeze_seconds=None)
    assert t.evaluate(50_000_000).severity is LagSeverity.NORMAL  # warning disabled
    assert t.evaluate(2_000_000_000).severity is LagSeverity.CRITICAL  # freeze disabled


def test_rejects_negative_thresholds() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        LagThresholds(warning_seconds=-1)


def test_rejects_inverted_ordering() -> None:
    with pytest.raises(ValueError, match="threshold ordering invalid"):
        LagThresholds(warning_seconds=1.0, critical_seconds=0.1)


def test_thresholds_round_trip_to_dict() -> None:
    t = LagThresholds(warning_seconds=0.05, critical_seconds=0.25, freeze_seconds=1.0)
    d = t.to_dict()
    assert d == {
        "warning_ns": 50_000_000,
        "critical_ns": 250_000_000,
        "freeze_ns": 1_000_000_000,
    }


def test_severity_is_orderable() -> None:
    # Ordered comparisons matter — the statistics aggregator uses ``>=``.
    assert LagSeverity.NORMAL < LagSeverity.WARNING < LagSeverity.CRITICAL < LagSeverity.FREEZE
    assert LagSeverity.CRITICAL >= LagSeverity.WARNING
