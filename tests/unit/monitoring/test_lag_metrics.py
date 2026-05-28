from __future__ import annotations

from asyncviz.runtime.monitoring.event_loop.lag_metrics import LagMetrics
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagSeverity


def test_metrics_start_at_zero() -> None:
    m = LagMetrics()
    snap = m.snapshot()
    assert snap.samples_attempted == 0
    assert snap.samples_recorded == 0
    assert snap.warning_threshold_hits == 0


def test_record_sample_recorded_resets_consecutive_drops() -> None:
    m = LagMetrics()
    m.record_sample_dropped()
    m.record_sample_dropped()
    assert m.snapshot().consecutive_drops == 2
    m.record_sample_recorded()
    assert m.snapshot().consecutive_drops == 0


def test_max_consecutive_drops_tracks_lifetime_peak() -> None:
    m = LagMetrics()
    for _ in range(5):
        m.record_sample_dropped()
    m.record_sample_recorded()  # resets consecutive
    for _ in range(3):
        m.record_sample_dropped()
    snap = m.snapshot()
    assert snap.max_consecutive_drops_observed == 5
    assert snap.consecutive_drops == 3


def test_threshold_hits_accumulate_with_severity() -> None:
    m = LagMetrics()
    m.record_threshold_hit(LagSeverity.WARNING)
    m.record_threshold_hit(LagSeverity.CRITICAL)
    m.record_threshold_hit(LagSeverity.FREEZE)
    snap = m.snapshot()
    # WARNING: warning(1) + critical(1) + freeze(1) = 3
    assert snap.warning_threshold_hits == 3
    # CRITICAL: critical(1) + freeze(1) = 2
    assert snap.critical_threshold_hits == 2
    # FREEZE: freeze(1) = 1
    assert snap.freeze_threshold_hits == 1


def test_scheduler_drift_accumulates_positive_deltas() -> None:
    m = LagMetrics()
    m.record_scheduler_drift(1_000)
    m.record_scheduler_drift(2_000)
    m.record_scheduler_drift(-5)  # ignored
    assert m.snapshot().scheduler_drift_ns == 3_000


def test_event_counters_independent() -> None:
    m = LagMetrics()
    m.record_measurement_event()
    m.record_measurement_event()
    m.record_threshold_breach_event()
    m.record_measurement_event_dropped()
    snap = m.snapshot()
    assert snap.measurement_events_emitted == 2
    assert snap.threshold_breach_events_emitted == 1
    assert snap.measurement_events_dropped == 1
