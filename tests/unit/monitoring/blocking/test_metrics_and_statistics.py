from __future__ import annotations

from asyncviz.runtime.monitoring.blocking.blocking_classifier import BlockingSeverity
from asyncviz.runtime.monitoring.blocking.blocking_metrics import BlockingMetrics
from asyncviz.runtime.monitoring.blocking.blocking_statistics import BlockingStatistics
from asyncviz.runtime.monitoring.blocking.blocking_windows import BlockingWindowSnapshot

# ── metrics ──────────────────────────────────────────────────────────────


def test_metrics_start_at_zero() -> None:
    m = BlockingMetrics()
    s = m.snapshot()
    assert s.measurements_processed == 0
    assert s.violations_total == 0
    assert all(v == 0 for v in s.violations_by_severity.values())


def test_violation_count_partitions_by_severity() -> None:
    m = BlockingMetrics()
    m.record_violation(BlockingSeverity.WARNING)
    m.record_violation(BlockingSeverity.WARNING)
    m.record_violation(BlockingSeverity.CRITICAL)
    m.record_violation(BlockingSeverity.FREEZE)
    s = m.snapshot()
    assert s.violations_total == 4
    assert s.violations_by_severity["WARNING"] == 2
    assert s.violations_by_severity["CRITICAL"] == 1
    assert s.violations_by_severity["FREEZE"] == 1


def test_escalation_counters_track_step() -> None:
    m = BlockingMetrics()
    m.record_escalation(
        from_severity=BlockingSeverity.WARNING,
        to_severity=BlockingSeverity.CRITICAL,
    )
    m.record_escalation(
        from_severity=BlockingSeverity.CRITICAL,
        to_severity=BlockingSeverity.FREEZE,
    )
    s = m.snapshot()
    assert s.escalations_warning_to_critical == 1
    assert s.escalations_critical_to_freeze == 1


def test_warning_to_freeze_escalation_counts_as_both_steps() -> None:
    m = BlockingMetrics()
    m.record_escalation(
        from_severity=BlockingSeverity.WARNING,
        to_severity=BlockingSeverity.FREEZE,
    )
    s = m.snapshot()
    assert s.escalations_warning_to_critical == 1
    assert s.escalations_critical_to_freeze == 1


def test_event_emission_accepted_vs_dropped() -> None:
    m = BlockingMetrics()
    m.record_violation_event(accepted=True)
    m.record_violation_event(accepted=False)
    m.record_window_event(accepted=True)
    m.record_escalation_event(accepted=False)
    s = m.snapshot()
    assert s.violation_events_emitted == 1
    assert s.violation_events_dropped == 1
    assert s.window_events_emitted == 1
    assert s.window_events_dropped == 0
    assert s.escalation_events_emitted == 0
    assert s.escalation_events_dropped == 1


# ── statistics ───────────────────────────────────────────────────────────


def _snapshot_window(
    *,
    window_id: str = "w1",
    open_ns: int = 0,
    close_ns: int = 1_000_000_000,
    peak_lag_ns: int = 5_000_000,
    peak_severity: BlockingSeverity = BlockingSeverity.WARNING,
    violation_count: int = 3,
) -> BlockingWindowSnapshot:
    return BlockingWindowSnapshot(
        window_id=window_id,
        runtime_id="r",
        open_sample_index=0,
        close_sample_index=5,
        open_monotonic_ns=open_ns,
        close_monotonic_ns=close_ns,
        peak_lag_ns=peak_lag_ns,
        peak_severity=peak_severity,
        violation_count=violation_count,
        escalation_count=0,
        closed=True,
    )


def test_statistics_empty_snapshot_has_zero_aggregates() -> None:
    s = BlockingStatistics().snapshot()
    assert s.windows_seen == 0
    assert s.longest_window_duration_ns == 0
    assert s.mean_window_duration_ns == 0


def test_statistics_track_longest_window() -> None:
    st = BlockingStatistics()
    st.observe_window_opened()
    st.observe_window_closed(_snapshot_window(window_id="w1", close_ns=1_000_000_000))
    st.observe_window_opened()
    st.observe_window_closed(
        _snapshot_window(window_id="w2", open_ns=2_000_000_000, close_ns=5_000_000_000)
    )
    s = st.snapshot()
    assert s.longest_window_duration_ns == 3_000_000_000
    assert s.longest_window_id == "w2"
    assert s.mean_window_duration_ns == 2_000_000_000


def test_statistics_partition_windows_by_peak_severity() -> None:
    st = BlockingStatistics()
    for sev in (
        BlockingSeverity.WARNING,
        BlockingSeverity.CRITICAL,
        BlockingSeverity.FREEZE,
        BlockingSeverity.WARNING,
    ):
        st.observe_window_opened()
        st.observe_window_closed(_snapshot_window(peak_severity=sev))
    s = st.snapshot()
    assert s.warning_windows == 2
    assert s.critical_windows == 1
    assert s.freeze_windows == 1


def test_statistics_lifetime_peak_survives_window_close() -> None:
    st = BlockingStatistics()
    st.observe_peak_lag(2_000_000_000)
    st.observe_window_closed(_snapshot_window(peak_lag_ns=500_000_000))
    s = st.snapshot()
    assert s.peak_lag_ns_lifetime == 2_000_000_000  # the orphan peak wins


def test_statistics_max_violation_count() -> None:
    st = BlockingStatistics()
    st.observe_window_closed(_snapshot_window(violation_count=3))
    st.observe_window_closed(_snapshot_window(violation_count=10))
    st.observe_window_closed(_snapshot_window(violation_count=2))
    assert st.snapshot().max_violation_count_in_window == 10
