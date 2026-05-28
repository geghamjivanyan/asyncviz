from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.blocking import BlockingSeverity
from asyncviz.runtime.warnings.blocking import (
    BlockingWarningPolicy,
    TransitionDeduplicator,
)
from asyncviz.runtime.warnings.blocking.utils import (
    build_synthetic_outcome,
    build_synthetic_window,
)

# ── policy ──────────────────────────────────────────────────────────────


def test_policy_rejects_none_severity() -> None:
    p = BlockingWarningPolicy()
    decision = p.evaluate(build_synthetic_outcome(severity=BlockingSeverity.NONE))
    assert decision.accept is False
    assert decision.reason == "severity_none"


def test_policy_rejects_below_min_severity_by_default() -> None:
    """Default min is CRITICAL — WARNING outcomes rejected."""
    p = BlockingWarningPolicy()
    decision = p.evaluate(
        build_synthetic_outcome(severity=BlockingSeverity.WARNING, window=build_synthetic_window())
    )
    assert decision.accept is False
    assert decision.reason == "below_min_severity"


def test_policy_accepts_critical_with_window() -> None:
    p = BlockingWarningPolicy()
    decision = p.evaluate(
        build_synthetic_outcome(severity=BlockingSeverity.CRITICAL, window=build_synthetic_window())
    )
    assert decision.accept is True


def test_policy_rejects_no_window_unless_opted_in() -> None:
    p = BlockingWarningPolicy()
    no_window = build_synthetic_outcome(severity=BlockingSeverity.CRITICAL)
    assert p.evaluate(no_window).accept is False
    p2 = BlockingWarningPolicy(include_no_window=True)
    assert p2.evaluate(no_window).accept is True


def test_policy_escalations_only_rejects_non_escalations() -> None:
    p = BlockingWarningPolicy(escalations_only=True)
    plain = build_synthetic_outcome(
        severity=BlockingSeverity.CRITICAL, window=build_synthetic_window()
    )
    assert p.evaluate(plain).reason == "escalations_only_non_escalation"
    escal = build_synthetic_outcome(
        severity=BlockingSeverity.FREEZE,
        window=build_synthetic_window(),
        escalated=True,
        escalation_from=BlockingSeverity.CRITICAL,
        escalation_to=BlockingSeverity.FREEZE,
    )
    assert p.evaluate(escal).accept is True


def test_policy_to_dict_round_trips_severity() -> None:
    p = BlockingWarningPolicy()
    d = p.to_dict()
    assert d["min_severity"] == "CRITICAL"
    assert d["include_no_window"] is False
    assert d["escalations_only"] is False


# ── deduplication ───────────────────────────────────────────────────────


def test_dedup_first_emission_passes() -> None:
    d = TransitionDeduplicator()
    decision = d.check_and_record(group_id="g1", transition="active", now_ns=0)
    assert decision.suppressed is False


def test_dedup_suppresses_repeat_within_window() -> None:
    d = TransitionDeduplicator(active_ns=1_000_000_000)
    d.check_and_record(group_id="g1", transition="active", now_ns=0)
    decision = d.check_and_record(group_id="g1", transition="active", now_ns=500_000_000)
    assert decision.suppressed is True
    assert decision.remaining_ns > 0


def test_dedup_zero_cooldown_means_no_suppression() -> None:
    d = TransitionDeduplicator(opened_ns=0)
    for ns in range(5):
        decision = d.check_and_record(group_id="g1", transition="opened", now_ns=ns)
        assert decision.suppressed is False


def test_dedup_is_per_transition() -> None:
    """An active cooldown doesn't suppress an escalation."""
    d = TransitionDeduplicator(active_ns=1_000_000_000)
    d.check_and_record(group_id="g1", transition="active", now_ns=0)
    decision = d.check_and_record(group_id="g1", transition="escalated", now_ns=0)
    assert decision.suppressed is False


def test_dedup_is_per_group() -> None:
    d = TransitionDeduplicator(active_ns=1_000_000_000)
    d.check_and_record(group_id="g1", transition="active", now_ns=0)
    decision = d.check_and_record(group_id="g2", transition="active", now_ns=0)
    assert decision.suppressed is False


def test_dedup_forget_group_clears_counters() -> None:
    d = TransitionDeduplicator(active_ns=1_000_000_000)
    d.check_and_record(group_id="g1", transition="active", now_ns=0)
    d.forget_group("g1")
    decision = d.check_and_record(group_id="g1", transition="active", now_ns=0)
    assert decision.suppressed is False


def test_dedup_rejects_negative_cooldown() -> None:
    with pytest.raises(ValueError, match="opened_ns must be >= 0"):
        TransitionDeduplicator(opened_ns=-1)


def test_dedup_to_dict_includes_each_kind() -> None:
    d = TransitionDeduplicator(
        opened_ns=1, escalated_ns=2, active_ns=3, recovered_ns=4, expired_ns=5
    )
    out = d.to_dict()
    assert out == {"opened": 1, "escalated": 2, "active": 3, "recovered": 4, "expired": 5}
