from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.blocking import BlockingSeverity
from asyncviz.runtime.monitoring.blocking.stack_capture import StackCapturePolicy

from ._helpers import build_outcome, make_window


def test_policy_skips_normal_severity() -> None:
    p = StackCapturePolicy()
    decision = p.decide(build_outcome(severity=BlockingSeverity.NONE))
    assert decision.capture is False


def test_policy_skips_below_min_severity_by_default() -> None:
    """Default min is CRITICAL — WARNINGs don't capture."""
    p = StackCapturePolicy(min_severity=BlockingSeverity.CRITICAL)
    decision = p.decide(build_outcome(severity=BlockingSeverity.WARNING))
    assert decision.capture is False


def test_policy_captures_warning_when_explicitly_opted_in() -> None:
    p = StackCapturePolicy(min_severity=BlockingSeverity.WARNING, capture_warning=True)
    decision = p.decide(build_outcome(severity=BlockingSeverity.WARNING))
    assert decision.capture is True


def test_policy_captures_first_violation_in_window() -> None:
    p = StackCapturePolicy(min_severity=BlockingSeverity.CRITICAL)
    decision = p.decide(build_outcome(severity=BlockingSeverity.CRITICAL, window=make_window()))
    assert decision.capture is True
    assert "first" in decision.trigger


def test_policy_caps_captures_per_window() -> None:
    p = StackCapturePolicy(min_severity=BlockingSeverity.CRITICAL, max_captures_per_window=2)
    win = make_window()
    decisions = [
        p.decide(build_outcome(severity=BlockingSeverity.CRITICAL, window=win, index=i))
        for i in range(5)
    ]
    captured = [d for d in decisions if d.capture]
    assert len(captured) == 2  # cap hit


def test_freeze_always_captures_bypassing_cap() -> None:
    p = StackCapturePolicy(min_severity=BlockingSeverity.CRITICAL, max_captures_per_window=1)
    win = make_window()
    # First CRITICAL takes the slot; freeze still goes through.
    p.decide(build_outcome(severity=BlockingSeverity.CRITICAL, window=win))
    decision = p.decide(build_outcome(severity=BlockingSeverity.FREEZE, window=win, index=1))
    assert decision.capture is True
    assert decision.trigger == "freeze"


def test_escalation_always_captures() -> None:
    p = StackCapturePolicy(min_severity=BlockingSeverity.CRITICAL, max_captures_per_window=1)
    win = make_window()
    p.decide(build_outcome(severity=BlockingSeverity.CRITICAL, window=win))
    decision = p.decide(
        build_outcome(
            severity=BlockingSeverity.CRITICAL,
            window=win,
            index=1,
            escalated=True,
            escalation_from=BlockingSeverity.WARNING,
            escalation_to=BlockingSeverity.CRITICAL,
        )
    )
    assert decision.capture is True
    assert decision.trigger == "escalation"


def test_captures_outside_windows_use_shared_bucket() -> None:
    p = StackCapturePolicy(
        min_severity=BlockingSeverity.CRITICAL,
        max_captures_per_window=1,
    )
    a = p.decide(build_outcome(severity=BlockingSeverity.CRITICAL, window=None))
    b = p.decide(build_outcome(severity=BlockingSeverity.CRITICAL, window=None, index=1))
    assert a.capture is True
    assert b.capture is False  # shared bucket cap hit


def test_each_window_has_independent_budget() -> None:
    p = StackCapturePolicy(min_severity=BlockingSeverity.CRITICAL, max_captures_per_window=1)
    w1 = make_window(window_id="r:bw:1")
    w2 = make_window(window_id="r:bw:2")
    a = p.decide(build_outcome(severity=BlockingSeverity.CRITICAL, window=w1))
    b = p.decide(build_outcome(severity=BlockingSeverity.CRITICAL, window=w2, index=1))
    assert a.capture is True
    assert b.capture is True


def test_reset_clears_window_counters() -> None:
    p = StackCapturePolicy(min_severity=BlockingSeverity.CRITICAL, max_captures_per_window=1)
    win = make_window()
    p.decide(build_outcome(severity=BlockingSeverity.CRITICAL, window=win))
    p.reset()
    decision = p.decide(build_outcome(severity=BlockingSeverity.CRITICAL, window=win, index=1))
    assert decision.capture is True


def test_invalid_max_captures_per_window_raises() -> None:
    with pytest.raises(ValueError, match="max_captures_per_window"):
        StackCapturePolicy(max_captures_per_window=0)


def test_policy_to_dict_round_trips_severity_names() -> None:
    p = StackCapturePolicy()
    d = p.to_dict()
    assert d["min_severity"] in {"NONE", "WARNING", "CRITICAL", "FREEZE"}
    assert d["always_capture_severity"] == "FREEZE"
