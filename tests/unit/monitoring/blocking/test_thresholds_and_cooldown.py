from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.blocking.blocking_classifier import BlockingSeverity
from asyncviz.runtime.monitoring.blocking.blocking_cooldown import BlockingCooldownPolicy
from asyncviz.runtime.monitoring.blocking.blocking_thresholds import BlockingThresholdPolicy

# ── thresholds ───────────────────────────────────────────────────────────


def test_default_threshold_policy_predicates() -> None:
    p = BlockingThresholdPolicy()
    assert p.is_violation(BlockingSeverity.NONE) is False
    assert p.is_violation(BlockingSeverity.WARNING) is True
    assert p.should_open_window(BlockingSeverity.NONE) is False
    assert p.should_open_window(BlockingSeverity.WARNING) is True


def test_threshold_policy_rejects_zero_close_consecutive() -> None:
    with pytest.raises(ValueError, match="window_close_consecutive_normals"):
        BlockingThresholdPolicy(window_close_consecutive_normals=0)


def test_threshold_policy_rejects_zero_escalation_warning() -> None:
    with pytest.raises(ValueError, match="escalation_warning_threshold"):
        BlockingThresholdPolicy(escalation_warning_threshold=0)


def test_threshold_policy_rejects_zero_escalation_critical() -> None:
    with pytest.raises(ValueError, match="escalation_critical_threshold"):
        BlockingThresholdPolicy(escalation_critical_threshold=0)


def test_threshold_policy_rejects_none_window_open() -> None:
    with pytest.raises(ValueError, match="window_open_severity must be > NONE"):
        BlockingThresholdPolicy(window_open_severity=BlockingSeverity.NONE)


def test_threshold_policy_to_dict_round_trips_severity_names() -> None:
    p = BlockingThresholdPolicy()
    d = p.to_dict()
    assert d["min_violation_severity"] == "WARNING"
    assert d["window_open_severity"] == "WARNING"


# ── cooldowns ────────────────────────────────────────────────────────────


def test_cooldown_accepts_first_event_then_suppresses_within_window() -> None:
    cp = BlockingCooldownPolicy(warning_ns=1_000_000_000)
    d1 = cp.check_and_record(BlockingSeverity.WARNING, now_ns=0)
    d2 = cp.check_and_record(BlockingSeverity.WARNING, now_ns=500_000_000)
    d3 = cp.check_and_record(BlockingSeverity.WARNING, now_ns=1_500_000_000)
    assert d1.suppressed is False
    assert d2.suppressed is True
    assert d2.remaining_ns > 0
    assert d3.suppressed is False  # cooldown elapsed


def test_cooldown_zero_means_no_suppression() -> None:
    cp = BlockingCooldownPolicy(freeze_ns=0)
    for i in range(5):
        d = cp.check_and_record(BlockingSeverity.FREEZE, now_ns=i)
        assert d.suppressed is False


def test_cooldown_is_per_severity() -> None:
    """A WARNING cooldown doesn't suppress a CRITICAL event."""
    cp = BlockingCooldownPolicy(warning_ns=1_000_000_000, critical_ns=1_000_000_000)
    cp.check_and_record(BlockingSeverity.WARNING, now_ns=0)
    crit = cp.check_and_record(BlockingSeverity.CRITICAL, now_ns=0)
    assert crit.suppressed is False


def test_cooldown_none_severity_always_passes() -> None:
    cp = BlockingCooldownPolicy()
    d = cp.check_and_record(BlockingSeverity.NONE, now_ns=0)
    assert d.suppressed is False
    assert d.remaining_ns == 0


def test_cooldown_reconfigure_preserves_last_emit() -> None:
    """Bumping the cooldown duration mid-flight still suppresses recent emits."""
    cp = BlockingCooldownPolicy(warning_ns=1_000_000)
    cp.check_and_record(BlockingSeverity.WARNING, now_ns=0)
    cp.configure(warning_ns=1_000_000_000)
    d = cp.check_and_record(BlockingSeverity.WARNING, now_ns=500_000)
    assert d.suppressed is True


def test_cooldown_to_dict_includes_each_severity() -> None:
    cp = BlockingCooldownPolicy(warning_ns=1, critical_ns=2, freeze_ns=3)
    d = cp.to_dict()
    assert d["WARNING"] == 1
    assert d["CRITICAL"] == 2
    assert d["FREEZE"] == 3
    assert d["NONE"] == 0


def test_cooldown_rejects_negative_durations() -> None:
    with pytest.raises(ValueError, match="warning_ns must be >= 0"):
        BlockingCooldownPolicy(warning_ns=-1)
