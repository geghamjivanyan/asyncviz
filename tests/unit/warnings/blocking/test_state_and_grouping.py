from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.blocking import BlockingSeverity
from asyncviz.runtime.warnings.blocking import (
    BlockingWarningGroupState,
    WarningGroup,
    WarningGroupRegistry,
)


def _build_group(
    *,
    group_id: str = "g1",
    window_id: str | None = "w1",
    severity: str = "CRITICAL",
    lag: int = 50_000_000,
    ns: int = 100,
) -> WarningGroup:
    return WarningGroup(
        group_id=group_id,
        warning_id=group_id,
        runtime_id="r",
        window_id=window_id,
        state=BlockingWarningGroupState.OPENED,
        severity=severity,
        peak_severity=severity,
        first_seen_ns=ns,
        last_seen_ns=ns,
        peak_lag_ns=lag,
        last_lag_ns=lag,
        violation_count=1,
        escalation_count=0,
    )


# ── state machine ──────────────────────────────────────────────────────


def test_state_is_open_predicate() -> None:
    for s in (
        BlockingWarningGroupState.OPENED,
        BlockingWarningGroupState.ESCALATING,
        BlockingWarningGroupState.ACTIVE,
    ):
        assert s.is_open is True
        assert s.is_terminal is False
    for s in (BlockingWarningGroupState.RECOVERED, BlockingWarningGroupState.EXPIRED):
        assert s.is_open is False
        assert s.is_terminal is True


# ── group observations ─────────────────────────────────────────────────


def test_record_observation_same_severity_marks_active() -> None:
    g = _build_group()
    new_state = g.record_observation(
        severity=BlockingSeverity.CRITICAL, lag_ns=60_000_000, monotonic_ns=200, sample_index=1
    )
    assert new_state is BlockingWarningGroupState.ACTIVE
    assert g.violation_count == 2
    assert g.peak_lag_ns == 60_000_000


def test_record_observation_higher_severity_escalates() -> None:
    g = _build_group(severity="CRITICAL")
    new_state = g.record_observation(
        severity=BlockingSeverity.FREEZE, lag_ns=200_000_000, monotonic_ns=200, sample_index=1
    )
    assert new_state is BlockingWarningGroupState.ESCALATING
    assert g.peak_severity == "FREEZE"
    assert g.severity == "FREEZE"
    assert g.escalation_count == 1
    assert len(g.escalation_history) == 1
    entry = g.escalation_history[0]
    assert entry.from_severity == "CRITICAL"
    assert entry.to_severity == "FREEZE"


def test_lower_severity_observation_does_not_lower_peak() -> None:
    g = _build_group(severity="FREEZE")
    g.peak_severity = "FREEZE"
    g.record_observation(
        severity=BlockingSeverity.CRITICAL, lag_ns=10_000_000, monotonic_ns=300, sample_index=2
    )
    assert g.peak_severity == "FREEZE"  # peak holds
    assert g.severity == "CRITICAL"  # current reflects latest


def test_attach_task_only_fills_empty_slots() -> None:
    g = _build_group()
    g.attach_task(task_id="t1", task_name="task-1", coroutine_name="cor")
    g.attach_task(task_id="t999", task_name="other", coroutine_name="other")
    assert g.task_id == "t1"
    assert g.task_name == "task-1"
    assert g.coroutine_name == "cor"


def test_record_capture_appends() -> None:
    g = _build_group()
    g.record_capture(1)
    g.record_capture(2)
    g.record_capture(3)
    assert g.capture_ids == [1, 2, 3]


def test_mark_recovered_transitions_state() -> None:
    g = _build_group()
    g.mark_recovered(monotonic_ns=500)
    assert g.state is BlockingWarningGroupState.RECOVERED
    assert g.recovered_ns == 500


def test_snapshot_freeze_duration_uses_recovered_ns() -> None:
    g = _build_group(ns=100)
    g.record_observation(
        severity=BlockingSeverity.CRITICAL, lag_ns=50_000_000, monotonic_ns=500, sample_index=1
    )
    g.mark_recovered(monotonic_ns=1100)
    snap = g.snapshot()
    assert snap.freeze_duration_ns == 1000  # 1100 - 100


# ── registry ───────────────────────────────────────────────────────────


def test_registry_lookup_by_window_id() -> None:
    reg = WarningGroupRegistry()
    g = _build_group(window_id="wA")
    reg.add(g)
    assert reg.find_by_window_id("wA") is g
    assert reg.find_by_window_id("missing") is None


def test_registry_finalize_moves_to_recent() -> None:
    reg = WarningGroupRegistry(recent_capacity=2)
    g = _build_group(group_id="g1", window_id="wA")
    reg.add(g)
    reg.finalize(g)
    assert reg.find_by_window_id("wA") is None
    assert reg.find_by_group_id("g1") is None
    recent = reg.recent_snapshots()
    assert len(recent) == 1


def test_registry_recent_ring_evicts_oldest() -> None:
    reg = WarningGroupRegistry(recent_capacity=2)
    for i in range(3):
        g = _build_group(group_id=f"g{i}", window_id=f"w{i}")
        reg.add(g)
        reg.finalize(g)
    recent = reg.recent_snapshots()
    assert len(recent) == 2
    assert [s.group_id for s in recent] == ["g1", "g2"]


def test_registry_rejects_zero_capacity() -> None:
    with pytest.raises(ValueError, match="recent_capacity must be > 0"):
        WarningGroupRegistry(recent_capacity=0)


def test_registry_sequence_increments() -> None:
    reg = WarningGroupRegistry()
    a = reg.next_sequence()
    b = reg.next_sequence()
    assert b == a + 1


def test_registry_reset_clears() -> None:
    reg = WarningGroupRegistry()
    g = _build_group()
    reg.add(g)
    reg.reset()
    assert reg.find_by_group_id(g.group_id) is None
    assert reg.recent_snapshots() == ()
