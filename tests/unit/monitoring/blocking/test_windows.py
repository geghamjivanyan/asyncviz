from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.blocking.blocking_classifier import (
    BlockingClassifier,
    BlockingSeverity,
)
from asyncviz.runtime.monitoring.blocking.blocking_escalation import EscalationEngine
from asyncviz.runtime.monitoring.blocking.blocking_thresholds import BlockingThresholdPolicy
from asyncviz.runtime.monitoring.blocking.blocking_windows import BlockingWindowTracker

from ._helpers import TIGHT_THRESHOLDS, measure


def _outcome(engine: EscalationEngine, lag_ns: int, *, index: int, scheduled_ns: int = 0):
    c = BlockingClassifier()
    m = measure(lag_ns, index=index, scheduled_ns=scheduled_ns)
    cls = c.classify(m, TIGHT_THRESHOLDS.evaluate(lag_ns))
    return engine.process(cls)


@pytest.fixture
def policy() -> BlockingThresholdPolicy:
    return BlockingThresholdPolicy(
        window_close_consecutive_normals=2,
        escalation_warning_threshold=100,  # disable for window tests
        escalation_critical_threshold=100,
    )


@pytest.fixture
def tracker(policy: BlockingThresholdPolicy) -> BlockingWindowTracker:
    return BlockingWindowTracker(policy=policy, runtime_id="r")


@pytest.fixture
def engine(policy: BlockingThresholdPolicy) -> EscalationEngine:
    return EscalationEngine(policy)


def test_window_opens_on_first_violation(tracker, engine) -> None:
    o = _outcome(engine, 1_000_000, index=0, scheduled_ns=0)
    t = tracker.process(o)
    assert t.opened is not None
    assert t.opened.open_sample_index == 0
    assert t.opened.violation_count == 1
    assert tracker.has_active() is True


def test_window_extends_on_subsequent_violations(tracker, engine) -> None:
    tracker.process(_outcome(engine, 1_000_000, index=0))
    t = tracker.process(_outcome(engine, 50_000_000, index=1, scheduled_ns=1_000))
    assert t.extended is not None
    assert t.extended.violation_count == 2
    assert t.extended.peak_lag_ns == 50_000_000
    assert t.extended.peak_severity is BlockingSeverity.CRITICAL


def test_window_closes_after_consecutive_normals(tracker, engine) -> None:
    tracker.process(_outcome(engine, 1_000_000, index=0))
    t1 = tracker.process(_outcome(engine, 0, index=1, scheduled_ns=1_000))
    assert t1.closed is None  # need 2 normals
    t2 = tracker.process(_outcome(engine, 0, index=2, scheduled_ns=2_000))
    assert t2.closed is not None
    assert t2.closed.closed is True
    assert tracker.has_active() is False


def test_window_close_marks_end_at_last_violation_not_recovery(tracker, engine) -> None:
    """The window's close timestamp should reflect the last symptom."""
    tracker.process(_outcome(engine, 1_000_000, index=0, scheduled_ns=10_000))
    tracker.process(_outcome(engine, 50_000_000, index=1, scheduled_ns=20_000))
    tracker.process(_outcome(engine, 0, index=2, scheduled_ns=30_000))
    t = tracker.process(_outcome(engine, 0, index=3, scheduled_ns=40_000))
    assert t.closed is not None
    # Last violation was at scheduled_ns=20_000 + lag(50_000_000) = 50_020_000
    assert t.closed.close_sample_index == 1
    assert t.closed.close_monotonic_ns == 20_000 + 50_000_000


def test_window_recovers_then_reopens_with_new_id(tracker, engine) -> None:
    tracker.process(_outcome(engine, 1_000_000, index=0))
    tracker.process(_outcome(engine, 0, index=1, scheduled_ns=1_000))
    tracker.process(_outcome(engine, 0, index=2, scheduled_ns=2_000))  # closes
    t = tracker.process(_outcome(engine, 1_000_000, index=3, scheduled_ns=3_000))
    assert t.opened is not None
    # Second window gets a distinct ID.
    assert t.opened.window_id.endswith(":bw:2")


def test_window_decays_then_resets_on_new_violation(tracker, engine) -> None:
    """A normal sample bumps the close counter; a new violation resets it."""
    tracker.process(_outcome(engine, 1_000_000, index=0))
    tracker.process(_outcome(engine, 0, index=1, scheduled_ns=1_000))  # 1 normal
    tracker.process(_outcome(engine, 1_000_000, index=2, scheduled_ns=2_000))  # reset
    t = tracker.process(_outcome(engine, 0, index=3, scheduled_ns=3_000))  # 1 normal
    assert t.closed is None
    assert tracker.has_active() is True


def test_history_capacity_evicts_oldest_window(policy) -> None:
    tracker = BlockingWindowTracker(policy=policy, runtime_id="r", history_capacity=2)
    engine = EscalationEngine(policy)
    # Create 3 windows.
    base = 0
    for _i in range(3):
        tracker.process(_outcome(engine, 1_000_000, index=base, scheduled_ns=base * 1000))
        base += 1
        tracker.process(_outcome(engine, 0, index=base, scheduled_ns=base * 1000))
        base += 1
        tracker.process(_outcome(engine, 0, index=base, scheduled_ns=base * 1000))
        base += 1
    history = tracker.history_snapshot()
    assert len(history) == 2  # oldest evicted
    assert tracker.total_closed == 3  # lifetime counter survives


def test_force_close_with_open_window(tracker, engine) -> None:
    tracker.process(_outcome(engine, 1_000_000, index=0, scheduled_ns=10_000))
    snap = tracker.force_close(monotonic_ns=999_999_999)
    assert snap is not None
    assert snap.closed is True
    assert tracker.has_active() is False


def test_force_close_with_no_open_window_returns_none(tracker) -> None:
    assert tracker.force_close(monotonic_ns=0) is None


def test_history_capacity_must_be_positive(policy) -> None:
    with pytest.raises(ValueError, match="history_capacity must be > 0"):
        BlockingWindowTracker(policy=policy, runtime_id="r", history_capacity=0)


def test_window_to_dict_contains_canonical_fields(tracker, engine) -> None:
    tracker.process(_outcome(engine, 1_000_000, index=0, scheduled_ns=0))
    tracker.process(_outcome(engine, 0, index=1, scheduled_ns=1_000))
    t = tracker.process(_outcome(engine, 0, index=2, scheduled_ns=2_000))
    d = t.closed.to_dict()
    for key in (
        "window_id",
        "open_sample_index",
        "close_sample_index",
        "open_monotonic_ns",
        "close_monotonic_ns",
        "peak_lag_ns",
        "peak_severity",
        "violation_count",
        "closed",
        "duration_ns",
    ):
        assert key in d
