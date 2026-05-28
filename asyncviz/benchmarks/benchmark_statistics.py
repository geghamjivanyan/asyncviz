"""Statistical aggregation for benchmark samples.

Pure functions over lists of integers (ns durations). No NumPy
dependency — the inputs are small + integer-valued so stdlib does
fine.

Outlier policies:

* ``none`` — keep everything.
* ``mad`` — drop samples whose deviation from the median exceeds
  ``threshold * MAD`` (median absolute deviation). Robust under
  skewed distributions where mean/stdev would mislead.
* ``iqr`` — drop samples outside ``[Q1 - factor*IQR, Q3 + factor*IQR]``
  (Tukey's fence).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

from asyncviz.benchmarks.benchmark_configuration import OutlierPolicy
from asyncviz.benchmarks.benchmark_models import (
    BenchmarkSample,
    BenchmarkStatistics,
)


def _percentile(sorted_values: Sequence[int], pct: float) -> int:
    if not sorted_values:
        return 0
    if pct <= 0:
        return sorted_values[0]
    if pct >= 100:
        return sorted_values[-1]
    # Use the "nearest rank" definition for stability across small N.
    rank = max(
        0,
        min(
            len(sorted_values) - 1,
            math.ceil(pct / 100.0 * len(sorted_values)) - 1,
        ),
    )
    return sorted_values[rank]


def _median(sorted_values: Sequence[int]) -> int:
    n = len(sorted_values)
    if n == 0:
        return 0
    mid = n // 2
    if n % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) // 2


def _mad(sorted_values: Sequence[int], median: int) -> int:
    if not sorted_values:
        return 0
    deviations = sorted(abs(v - median) for v in sorted_values)
    return _median(deviations)


def apply_outlier_policy(
    durations_ns: Sequence[int],
    *,
    policy: OutlierPolicy,
    mad_threshold: float,
    iqr_factor: float,
) -> tuple[list[int], int]:
    """Return ``(kept_samples, excluded_count)``."""
    if not durations_ns or policy == "none":
        return list(durations_ns), 0
    sorted_values = sorted(durations_ns)
    if policy == "mad":
        median = _median(sorted_values)
        mad = _mad(sorted_values, median)
        if mad == 0:
            # MAD=0 means most samples sit on the median. Anything
            # that doesn't is an outlier by definition (point-mass
            # distribution). Keep only the samples that match the
            # median; if literally all samples are identical this
            # collapses to keeping everything.
            kept = [v for v in durations_ns if v == median]
            return kept, len(durations_ns) - len(kept)
        threshold = int(mad_threshold * mad)
        kept = [v for v in durations_ns if abs(v - median) <= threshold]
        return kept, len(durations_ns) - len(kept)
    if policy == "iqr":
        q1 = _percentile(sorted_values, 25.0)
        q3 = _percentile(sorted_values, 75.0)
        iqr = q3 - q1
        lo = int(q1 - iqr_factor * iqr)
        hi = int(q3 + iqr_factor * iqr)
        kept = [v for v in durations_ns if lo <= v <= hi]
        return kept, len(durations_ns) - len(kept)
    return list(durations_ns), 0


def aggregate_samples(
    samples: Sequence[BenchmarkSample],
    *,
    policy: OutlierPolicy = "mad",
    mad_threshold: float = 3.5,
    iqr_factor: float = 1.5,
) -> BenchmarkStatistics:
    """Compute per-spec statistics with outlier filtering applied."""
    durations = [s.duration_ns for s in samples]
    allocations = [s.allocations_delta_bytes for s in samples]
    kept, excluded = apply_outlier_policy(
        durations,
        policy=policy,
        mad_threshold=mad_threshold,
        iqr_factor=iqr_factor,
    )
    sorted_kept = sorted(kept)
    if not sorted_kept:
        return BenchmarkStatistics(
            sample_count=0,
            samples_excluded=excluded,
            median_ns=0,
            mean_ns=0,
            min_ns=0,
            max_ns=0,
            stdev_ns=0,
            p95_ns=0,
            p99_ns=0,
            coefficient_of_variation=0.0,
        )
    mean = int(statistics.fmean(sorted_kept))
    stdev = int(statistics.pstdev(sorted_kept)) if len(sorted_kept) > 1 else 0
    cv = stdev / mean if mean > 0 else 0.0
    cumulative_alloc = sum(allocations)
    max_alloc = max(allocations) if allocations else 0
    return BenchmarkStatistics(
        sample_count=len(sorted_kept),
        samples_excluded=excluded,
        median_ns=_median(sorted_kept),
        mean_ns=mean,
        min_ns=sorted_kept[0],
        max_ns=sorted_kept[-1],
        stdev_ns=stdev,
        p95_ns=_percentile(sorted_kept, 95.0),
        p99_ns=_percentile(sorted_kept, 99.0),
        coefficient_of_variation=cv,
        cumulative_allocations_bytes=cumulative_alloc,
        max_allocation_delta_bytes=max_alloc,
    )
