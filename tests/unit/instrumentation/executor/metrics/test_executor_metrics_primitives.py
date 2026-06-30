"""Standalone tests for the metrics building blocks (utilization
window, latency digest, throughput counters, saturation scorer,
utilization tracker)."""

from __future__ import annotations

import pytest

from asyncviz.instrumentation.executor.metrics.executor_metrics_configuration import (
    ExecutorMetricsConfig,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_saturation import (
    SaturationScorer,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_statistics import (
    LatencyDigest,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_throughput import (
    ThroughputCounters,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_utilization import (
    UtilizationTracker,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_windows import (
    UtilizationWindow,
)

# ── UtilizationWindow ────────────────────────────────────────────────────


def test_window_tracks_peak_and_mean() -> None:
    w = UtilizationWindow(capacity=4)
    for n in (0, 2, 4, 6):
        w.observe(n)
    assert w.peak == 6
    assert w.mean() == 3.0


def test_window_evicts_when_full() -> None:
    w = UtilizationWindow(capacity=3)
    for n in (1, 2, 3, 4, 5):
        w.observe(n)
    assert list(w.samples) == [3, 4, 5]
    assert w.mean() == 4.0
    assert w.peak == 5


def test_window_rejects_capacity_zero() -> None:
    with pytest.raises(ValueError):
        UtilizationWindow(capacity=0)


# ── UtilizationTracker ──────────────────────────────────────────────────


def test_tracker_increments_and_decrements() -> None:
    t = UtilizationTracker(window=UtilizationWindow(capacity=4), max_workers=4)
    t.increment()
    t.increment()
    snap = t.snapshot()
    assert snap.active_workers == 2
    assert snap.utilization_ratio == 0.5
    t.decrement()
    assert t.snapshot().active_workers == 1


def test_tracker_decrement_floor_at_zero() -> None:
    t = UtilizationTracker(window=UtilizationWindow(capacity=4), max_workers=4)
    t.decrement()
    assert t.active_workers == 0


def test_tracker_updates_max_workers_late() -> None:
    t = UtilizationTracker(window=UtilizationWindow(capacity=4), max_workers=None)
    t.increment()
    assert t.snapshot().utilization_ratio == 0.0
    t.update_max_workers(2)
    assert t.snapshot().utilization_ratio == 0.5


# ── LatencyDigest ───────────────────────────────────────────────────────


def test_latency_digest_running_mean_is_exact() -> None:
    d = LatencyDigest(capacity=4)
    for s in (0.1, 0.2, 0.3, 0.4):
        d.observe(s)
    snap = d.snapshot()
    assert snap.count == 4
    assert snap.mean_seconds == pytest.approx(0.25)
    assert snap.max_seconds == pytest.approx(0.4)


def test_latency_digest_clamps_negative() -> None:
    d = LatencyDigest(capacity=4)
    d.observe(-1.0)
    assert d.snapshot().mean_seconds == 0.0


def test_latency_digest_reservoir_caps() -> None:
    d = LatencyDigest(capacity=8)
    for s in range(100):
        d.observe(float(s) / 100)
    snap = d.snapshot()
    assert snap.count == 100
    assert 0.85 <= snap.p99_seconds <= 1.0


# ── ThroughputCounters ──────────────────────────────────────────────────


def test_throughput_tracks_lifecycle_counts() -> None:
    t = ThroughputCounters(window_seconds=10)
    for i in range(5):
        t.record_submission(monotonic_seconds=float(i))
    for i in range(3):
        t.record_completion(monotonic_seconds=float(i + 1))
    t.record_failure(monotonic_seconds=1.0)
    t.record_cancellation(monotonic_seconds=1.0)
    snap = t.snapshot(monotonic_seconds=5.0)
    assert snap.submissions == 5
    assert snap.completions == 3
    assert snap.failures == 1
    assert snap.cancellations == 1
    assert snap.backlog == 0


def test_throughput_rate_decays_when_idle() -> None:
    t = ThroughputCounters(window_seconds=5)
    t.record_submission(monotonic_seconds=0.0)
    assert t.snapshot(monotonic_seconds=100.0).submission_rate == pytest.approx(0.0)


# ── SaturationScorer ────────────────────────────────────────────────────


@pytest.fixture
def hysteretic_config() -> ExecutorMetricsConfig:
    return ExecutorMetricsConfig(
        saturation_warning_threshold=0.6,
        saturation_critical_threshold=0.85,
        saturation_hysteresis=0.05,
    )


def test_saturation_calm_to_warning_to_critical(
    hysteretic_config: ExecutorMetricsConfig,
) -> None:
    s = SaturationScorer(config=hysteretic_config)
    calm = s.evaluate(
        utilization_ratio=0.1,
        max_workers=4,
        backlog=0,
        submission_rate=1.0,
        completion_rate=1.0,
        mean_submission_latency=0.0,
    )
    assert calm.level == "calm"

    warning = s.evaluate(
        utilization_ratio=0.8,
        max_workers=4,
        backlog=4,
        submission_rate=10.0,
        completion_rate=2.0,
        mean_submission_latency=0.05,
    )
    assert warning.level == "warning"

    critical = s.evaluate(
        utilization_ratio=0.95,
        max_workers=4,
        backlog=16,
        submission_rate=20.0,
        completion_rate=1.0,
        mean_submission_latency=0.5,
    )
    assert critical.level == "critical"


def test_saturation_hysteresis_no_flicker(
    hysteretic_config: ExecutorMetricsConfig,
) -> None:
    s = SaturationScorer(config=hysteretic_config)
    s.evaluate(
        utilization_ratio=1.0,
        max_workers=4,
        backlog=20,
        submission_rate=20.0,
        completion_rate=0.0,
        mean_submission_latency=1.0,
    )
    assert s.level == "critical"
    # Score drops slightly below the critical line but above the hysteresis
    # margin (0.85 - 0.05 = 0.80) — should stay critical.
    s.evaluate(
        utilization_ratio=1.0,
        max_workers=4,
        backlog=8,
        submission_rate=2.0,
        completion_rate=2.0,
        mean_submission_latency=0.1,
    )
    assert s.level == "critical"
    # Drop well below — now can de-escalate.
    cooled = s.evaluate(
        utilization_ratio=0.1,
        max_workers=4,
        backlog=0,
        submission_rate=0.5,
        completion_rate=0.5,
        mean_submission_latency=0.0,
    )
    assert cooled.level in {"warning", "calm"}
