from __future__ import annotations

from asyncviz.runtime.monitoring.blocking.blocking_classifier import (
    BlockingClassifier,
    BlockingSeverity,
)
from asyncviz.runtime.monitoring.blocking.blocking_escalation import EscalationEngine
from asyncviz.runtime.monitoring.blocking.blocking_thresholds import BlockingThresholdPolicy

from ._helpers import TIGHT_THRESHOLDS, measure


def _classify(lag_ns: int, *, index: int = 0):
    c = BlockingClassifier()
    return c.classify(measure(lag_ns, index=index), TIGHT_THRESHOLDS.evaluate(lag_ns))


def test_no_escalation_below_threshold() -> None:
    e = EscalationEngine(BlockingThresholdPolicy(escalation_warning_threshold=5))
    for i in range(4):
        outcome = e.process(_classify(1_000_000, index=i))  # WARNING
        assert outcome.effective_severity is BlockingSeverity.WARNING
        assert outcome.escalated is False


def test_warning_escalates_after_threshold_count() -> None:
    e = EscalationEngine(BlockingThresholdPolicy(escalation_warning_threshold=3))
    out1 = e.process(_classify(1_000_000, index=0))
    out2 = e.process(_classify(1_000_000, index=1))
    out3 = e.process(_classify(1_000_000, index=2))  # 3rd → escalate
    out4 = e.process(_classify(1_000_000, index=3))  # still CRITICAL
    assert out1.effective_severity is BlockingSeverity.WARNING
    assert out2.effective_severity is BlockingSeverity.WARNING
    assert out3.effective_severity is BlockingSeverity.CRITICAL
    assert out3.escalated is True
    assert out3.escalation_from is BlockingSeverity.WARNING
    assert out3.escalation_to is BlockingSeverity.CRITICAL
    assert out4.effective_severity is BlockingSeverity.CRITICAL


def test_critical_escalates_to_freeze() -> None:
    e = EscalationEngine(BlockingThresholdPolicy(escalation_critical_threshold=2))
    out1 = e.process(_classify(50_000_000, index=0))  # CRITICAL
    out2 = e.process(_classify(50_000_000, index=1))  # 2nd → escalate
    assert out1.effective_severity is BlockingSeverity.CRITICAL
    assert out2.effective_severity is BlockingSeverity.FREEZE
    assert out2.escalated is True


def test_normal_sample_resets_warning_counter() -> None:
    e = EscalationEngine(BlockingThresholdPolicy(escalation_warning_threshold=3))
    e.process(_classify(1_000_000))
    e.process(_classify(1_000_000))
    e.process(_classify(0))  # NORMAL — reset warning counter
    out = e.process(_classify(1_000_000))
    assert out.effective_severity is BlockingSeverity.WARNING
    assert out.escalated is False
    assert out.consecutive_warning == 1


def test_consecutive_counts_track_source_not_effective() -> None:
    """Escalating to CRITICAL doesn't artificially bump CRITICAL counter.

    Otherwise a single WARNING storm would also escalate to FREEZE.
    """
    e = EscalationEngine(
        BlockingThresholdPolicy(
            escalation_warning_threshold=2,
            escalation_critical_threshold=2,
        )
    )
    for i in range(10):  # 10 consecutive WARNINGs
        out = e.process(_classify(1_000_000, index=i))
    # Should stop at CRITICAL — never reach FREEZE since source is always WARNING
    assert out.effective_severity is BlockingSeverity.CRITICAL


def test_freeze_severity_passes_through_unchanged() -> None:
    e = EscalationEngine(BlockingThresholdPolicy())
    out = e.process(_classify(500_000_000))  # FREEZE
    assert out.effective_severity is BlockingSeverity.FREEZE
    assert out.escalated is False


def test_reset_clears_counters() -> None:
    e = EscalationEngine(BlockingThresholdPolicy(escalation_warning_threshold=3))
    for _ in range(2):
        e.process(_classify(1_000_000))
    e.reset()
    out = e.process(_classify(1_000_000))
    assert out.consecutive_warning == 1


def test_reconfigure_preserves_counters() -> None:
    e = EscalationEngine(BlockingThresholdPolicy(escalation_warning_threshold=10))
    for _ in range(3):
        e.process(_classify(1_000_000))
    # Tighten the threshold — the existing counters should immediately
    # cross it.
    e.configure(BlockingThresholdPolicy(escalation_warning_threshold=3))
    out = e.process(_classify(1_000_000))
    assert out.effective_severity is BlockingSeverity.CRITICAL
