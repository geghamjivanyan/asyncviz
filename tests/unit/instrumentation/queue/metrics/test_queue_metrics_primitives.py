"""Standalone tests for the metrics building blocks (occupancy window,
wait digest, throughput counters, pressure scorer, contention tracker).

These don't touch the engine — fast, deterministic, no async."""

from __future__ import annotations

import pytest

from asyncviz.instrumentation.queue.metrics.queue_metrics_configuration import (
    QueueMetricsConfig,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_contention import (
    ContentionTracker,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_pressure import (
    PressureScorer,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_statistics import (
    WaitDigest,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_throughput import (
    ThroughputCounters,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_windows import (
    OccupancyWindow,
)

# ── OccupancyWindow ──────────────────────────────────────────────────────


def test_occupancy_window_tracks_peak_and_mean() -> None:
    w = OccupancyWindow(capacity=4)
    for size in (0, 2, 4, 6):
        w.observe(size)
    assert w.peak == 6
    assert w.mean() == 3.0  # (0+2+4+6)/4


def test_occupancy_window_evicts_when_full() -> None:
    w = OccupancyWindow(capacity=3)
    for size in (1, 2, 3, 4, 5):
        w.observe(size)
    # only the last 3 remain
    assert list(w.samples) == [3, 4, 5]
    assert w.mean() == 4.0
    # peak is sticky even if the high value rolled out
    assert w.peak == 5


def test_occupancy_window_rejects_capacity_zero() -> None:
    with pytest.raises(ValueError):
        OccupancyWindow(capacity=0)


def test_occupancy_window_reset() -> None:
    w = OccupancyWindow(capacity=4)
    w.observe(10)
    w.reset()
    assert w.peak == 0
    assert w.mean() == 0.0
    assert len(w.samples) == 0


# ── WaitDigest ───────────────────────────────────────────────────────────


def test_wait_digest_running_mean_is_exact() -> None:
    d = WaitDigest(capacity=4)
    for s in (0.1, 0.2, 0.3, 0.4):
        d.observe(s)
    snap = d.snapshot()
    assert snap.count == 4
    assert snap.mean_seconds == pytest.approx(0.25)
    assert snap.max_seconds == pytest.approx(0.4)


def test_wait_digest_reservoir_caps_at_capacity() -> None:
    d = WaitDigest(capacity=8)
    # 100 samples in a fixed range — percentile is approximate but bounded.
    for s in range(100):
        d.observe(float(s) / 100)
    snap = d.snapshot()
    assert snap.count == 100
    # only the most recent 8 samples drive the percentile reservoir
    assert 0.85 <= snap.p99_seconds <= 1.0


def test_wait_digest_clamps_negative_to_zero() -> None:
    d = WaitDigest(capacity=4)
    d.observe(-1.0)
    snap = d.snapshot()
    assert snap.mean_seconds == 0.0


def test_wait_digest_empty_snapshot() -> None:
    d = WaitDigest(capacity=4)
    snap = d.snapshot()
    assert snap.count == 0
    assert snap.mean_seconds == 0.0
    assert snap.max_seconds == 0.0


# ── ThroughputCounters ──────────────────────────────────────────────────


def test_throughput_counts_puts_and_gets() -> None:
    t = ThroughputCounters(window_seconds=10)
    for i in range(5):
        t.record_put(monotonic_seconds=float(i), nowait=False)
    for i in range(3):
        t.record_get(monotonic_seconds=float(i + 1), nowait=True)
    snap = t.snapshot(monotonic_seconds=5.0)
    assert snap.put_count == 5
    assert snap.get_count == 3
    assert snap.producer_consumer_delta == 2
    assert t.nowait_get_count == 3


def test_throughput_rate_decays_when_idle() -> None:
    t = ThroughputCounters(window_seconds=5)
    t.record_put(monotonic_seconds=0.0, nowait=False)
    fresh = t.snapshot(monotonic_seconds=0.5).put_rate
    decayed = t.snapshot(monotonic_seconds=100.0).put_rate
    assert decayed == pytest.approx(0.0)
    assert fresh >= 0.0


# ── ContentionTracker ────────────────────────────────────────────────────


def test_contention_tracker_records_peaks() -> None:
    c = ContentionTracker()
    c.update_blocked(producers=2, consumers=0)
    c.update_blocked(producers=5, consumers=3)
    c.update_blocked(producers=1, consumers=1)
    snap = c.snapshot()
    assert snap.peak_blocked_producers == 5
    assert snap.peak_blocked_consumers == 3
    # current view is the last update
    assert snap.blocked_producers == 1
    assert snap.blocked_consumers == 1


def test_contention_tracker_lifetime_counters() -> None:
    c = ContentionTracker()
    c.record_blocked_put()
    c.record_blocked_put()
    c.record_blocked_get()
    c.record_full_wait()
    c.record_empty_wait()
    c.record_cancelled()
    snap = c.snapshot()
    assert snap.blocked_put_count == 2
    assert snap.blocked_get_count == 1
    assert snap.full_wait_count == 1
    assert snap.empty_wait_count == 1
    assert snap.cancelled_count == 1


# ── PressureScorer ───────────────────────────────────────────────────────


@pytest.fixture
def hysteretic_config() -> QueueMetricsConfig:
    return QueueMetricsConfig(
        pressure_warning_threshold=0.6,
        pressure_critical_threshold=0.85,
        pressure_hysteresis=0.05,
    )


def test_pressure_calm_to_warning_to_critical(
    hysteretic_config: QueueMetricsConfig,
) -> None:
    scorer = PressureScorer(config=hysteretic_config)
    calm = scorer.evaluate(
        occupancy_ratio=0.1,
        blocked_producers=0,
        blocked_consumers=0,
        put_rate=1.0,
        get_rate=1.0,
    )
    assert calm.level == "calm"

    warning = scorer.evaluate(
        occupancy_ratio=0.85,
        blocked_producers=4,
        blocked_consumers=0,
        put_rate=8.0,
        get_rate=2.0,
    )
    assert warning.level == "warning"

    critical = scorer.evaluate(
        occupancy_ratio=0.95,
        blocked_producers=8,
        blocked_consumers=8,
        put_rate=10.0,
        get_rate=1.0,
    )
    assert critical.level == "critical"


def test_pressure_hysteresis_prevents_flicker(
    hysteretic_config: QueueMetricsConfig,
) -> None:
    scorer = PressureScorer(config=hysteretic_config)
    # Push into critical.
    scorer.evaluate(
        occupancy_ratio=0.95,
        blocked_producers=10,
        blocked_consumers=10,
        put_rate=5.0,
        get_rate=0.0,
    )
    assert scorer.level == "critical"
    # A score that's just below the critical threshold but above
    # ``critical - hysteresis`` (0.80) must NOT de-escalate. With
    # occ=0.92, half-saturated blocked ratio, and full-velocity skew the
    # composite score lands at ~0.81 — inside the hysteresis band.
    barely_below = scorer.evaluate(
        occupancy_ratio=0.92,
        blocked_producers=4,
        blocked_consumers=4,
        put_rate=5.0,
        get_rate=0.0,
    )
    assert barely_below.level == "critical"
    # Well below — now it can drop to warning or calm.
    cooled = scorer.evaluate(
        occupancy_ratio=0.3,
        blocked_producers=0,
        blocked_consumers=0,
        put_rate=1.0,
        get_rate=1.0,
    )
    assert cooled.level in {"warning", "calm"}


def test_pressure_saturation_ratio_is_sticky(
    hysteretic_config: QueueMetricsConfig,
) -> None:
    scorer = PressureScorer(config=hysteretic_config)
    scorer.evaluate(
        occupancy_ratio=0.92,
        blocked_producers=0,
        blocked_consumers=0,
        put_rate=0.0,
        get_rate=0.0,
    )
    scorer.evaluate(
        occupancy_ratio=0.1,
        blocked_producers=0,
        blocked_consumers=0,
        put_rate=0.0,
        get_rate=0.0,
    )
    # The high-water-mark survives a subsequent quiet sample.
    assert scorer.saturation_ratio == pytest.approx(0.92)
