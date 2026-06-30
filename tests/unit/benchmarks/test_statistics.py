"""Statistics aggregation tests."""

from __future__ import annotations

from asyncviz.benchmarks import BenchmarkSample, aggregate_samples
from asyncviz.benchmarks.benchmark_statistics import apply_outlier_policy


def _samples(durations_ns: list[int]) -> list[BenchmarkSample]:
    return [BenchmarkSample(duration_ns=d) for d in durations_ns]


def test_aggregate_basic_statistics() -> None:
    samples = _samples([100, 200, 300, 400, 500])
    stats = aggregate_samples(samples, policy="none")
    assert stats.sample_count == 5
    assert stats.median_ns == 300
    assert stats.min_ns == 100
    assert stats.max_ns == 500
    assert stats.p95_ns == 500
    assert stats.p99_ns == 500
    assert stats.coefficient_of_variation > 0


def test_aggregate_single_sample() -> None:
    stats = aggregate_samples(_samples([42]), policy="none")
    assert stats.sample_count == 1
    assert stats.median_ns == 42
    assert stats.stdev_ns == 0


def test_aggregate_empty_samples() -> None:
    stats = aggregate_samples([], policy="none")
    assert stats.sample_count == 0
    assert stats.median_ns == 0


def test_mad_outlier_filtering_drops_far_samples() -> None:
    base = [100] * 20
    base.extend([100_000, 100_000])  # extreme outliers
    kept, excluded = apply_outlier_policy(
        base,
        policy="mad",
        mad_threshold=3.5,
        iqr_factor=1.5,
    )
    assert excluded == 2
    assert len(kept) == 20


def test_iqr_outlier_filtering_drops_extreme_tail() -> None:
    base = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 1_000_000]
    _kept, excluded = apply_outlier_policy(
        base,
        policy="iqr",
        mad_threshold=3.5,
        iqr_factor=1.5,
    )
    assert excluded == 1


def test_none_policy_keeps_everything() -> None:
    base = [1, 2, 3, 4, 5, 1_000_000]
    kept, excluded = apply_outlier_policy(
        base,
        policy="none",
        mad_threshold=3.5,
        iqr_factor=1.5,
    )
    assert excluded == 0
    assert kept == base


def test_aggregate_with_allocation_tracking() -> None:
    samples = [
        BenchmarkSample(duration_ns=100, allocations_delta_bytes=1024),
        BenchmarkSample(duration_ns=200, allocations_delta_bytes=2048),
    ]
    stats = aggregate_samples(samples, policy="none")
    assert stats.cumulative_allocations_bytes == 3072
    assert stats.max_allocation_delta_bytes == 2048
