from __future__ import annotations

import pytest

from asyncviz.runtime.monitoring.event_loop.lag_measurement import calculate_lag
from asyncviz.runtime.monitoring.event_loop.lag_statistics import LagStatistics
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import (
    LagSeverity,
)


def _measure(lag_ns: int, *, index: int = 0):
    return calculate_lag(
        scheduled_ns=0,
        actual_ns=lag_ns,
        interval_ns=100_000_000,
        sample_index=index,
        runtime_id="r",
    )


def test_empty_snapshot_has_zero_aggregates() -> None:
    s = LagStatistics(window=4)
    snap = s.snapshot()
    assert snap.sample_count == 0
    assert snap.window_filled == 0
    assert snap.mean_ns == 0
    assert snap.p99_ns == 0


def test_window_evicts_oldest_when_full() -> None:
    s = LagStatistics(window=3)
    for i, lag in enumerate([100, 200, 300, 400]):
        s.observe(_measure(lag, index=i), LagSeverity.NORMAL)
    snap = s.snapshot()
    # 100 was evicted; window now [200, 300, 400] with sum 900
    assert snap.window_filled == 3
    assert snap.sum_ns == 900
    assert snap.min_ns == 200
    assert snap.max_ns == 400
    assert snap.mean_ns == 300
    assert snap.sample_count == 4


def test_peak_tracks_lifetime_maximum_not_window() -> None:
    """Peak survives even after the spike is evicted from the window."""
    s = LagStatistics(window=2)
    for i, lag in enumerate([1_000_000_000, 1, 2]):
        s.observe(_measure(lag, index=i), LagSeverity.NORMAL)
    snap = s.snapshot()
    assert snap.peak_ns == 1_000_000_000
    assert snap.window_filled == 2
    assert snap.max_ns == 2  # window-local max


def test_percentiles_match_nearest_rank() -> None:
    s = LagStatistics(window=100)
    for i, lag in enumerate(range(1, 101)):
        s.observe(_measure(lag, index=i), LagSeverity.NORMAL)
    snap = s.snapshot()
    # Nearest-rank: p50 → ceil(0.5 * 100) - 0-indexed = 49 → value 50
    assert snap.p50_ns == 50
    assert snap.p95_ns == 95
    assert snap.p99_ns == 99
    assert snap.min_ns == 1
    assert snap.max_ns == 100


def test_consecutive_warning_counter_resets_on_normal() -> None:
    s = LagStatistics(window=10)
    s.observe(_measure(10), LagSeverity.WARNING)
    s.observe(_measure(20), LagSeverity.WARNING)
    s.observe(_measure(30), LagSeverity.WARNING)
    snap = s.snapshot()
    assert snap.consecutive_warning_count == 3
    s.observe(_measure(40), LagSeverity.NORMAL)
    snap = s.snapshot()
    assert snap.consecutive_warning_count == 0


def test_freeze_segment_tracking() -> None:
    s = LagStatistics(window=10)
    s.observe(_measure(1_000_000_000), LagSeverity.FREEZE)
    s.observe(_measure(2_000_000_000), LagSeverity.FREEZE)
    snap = s.snapshot()
    assert snap.consecutive_freeze_count == 2
    assert snap.freeze_segments == 1
    assert snap.last_freeze_duration_ns == 3_000_000_000
    assert snap.longest_freeze_duration_ns == 3_000_000_000

    # Exit freeze
    s.observe(_measure(10), LagSeverity.NORMAL)
    snap = s.snapshot()
    assert snap.consecutive_freeze_count == 0
    assert snap.freeze_segments == 1

    # New freeze
    s.observe(_measure(5_000_000_000), LagSeverity.FREEZE)
    snap = s.snapshot()
    assert snap.freeze_segments == 2
    assert snap.last_freeze_duration_ns == 5_000_000_000
    assert snap.longest_freeze_duration_ns == 5_000_000_000


def test_reset_clears_window_and_lifetime_counters() -> None:
    s = LagStatistics(window=4)
    s.observe(_measure(100), LagSeverity.WARNING)
    s.reset()
    snap = s.snapshot()
    assert snap.sample_count == 0
    assert snap.peak_ns == 0
    assert snap.consecutive_warning_count == 0


def test_window_must_be_positive() -> None:
    with pytest.raises(ValueError, match="window must be > 0"):
        LagStatistics(window=0)


def test_snapshot_is_deterministic_for_identical_sequences() -> None:
    """Same input sequence → byte-identical snapshot. Replay safety."""

    def build():
        s = LagStatistics(window=8)
        for i, lag in enumerate([10, 20, 30, 40, 1_000, 50, 60, 70]):
            sev = LagSeverity.WARNING if lag > 100 else LagSeverity.NORMAL
            s.observe(_measure(lag, index=i), sev)
        return s.snapshot().to_dict()

    assert build() == build()
