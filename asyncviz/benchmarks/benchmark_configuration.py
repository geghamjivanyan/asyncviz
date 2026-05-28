"""Benchmark configuration.

Centralizes every knob the runner cares about: warmup discipline,
sample counts, statistical rigor (outlier policy, minimum-sample
floor), default regression thresholds. Tests construct purpose-built
configs; the production CLI uses :func:`default_config`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

OutlierPolicy = Literal["none", "mad", "iqr"]
"""How outliers are excluded from the reported statistics.

* ``none`` — keep every sample.
* ``mad`` (default) — drop samples beyond a configured number of
  median-absolute-deviations from the median. Stable under skewed
  distributions where mean/stdev would mislead.
* ``iqr`` — Tukey's IQR fence.
"""

DEFAULT_WARMUP_ITERATIONS: Final[int] = 50
DEFAULT_MEASURED_ITERATIONS: Final[int] = 500
DEFAULT_MIN_SAMPLES: Final[int] = 25
"""Hard floor — a benchmark with fewer surviving samples than this
is flagged as ``insufficient`` rather than reported with bogus
statistics."""

DEFAULT_REGRESSION_THRESHOLD: Final[float] = 0.15
"""Default ±15% p95 swing before a regression is declared."""

DEFAULT_REPORT_PERCENTILES: Final[tuple[float, ...]] = (50.0, 95.0, 99.0)


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    """Immutable benchmark-runner configuration."""

    warmup_iterations: int = DEFAULT_WARMUP_ITERATIONS
    measured_iterations: int = DEFAULT_MEASURED_ITERATIONS
    min_samples: int = DEFAULT_MIN_SAMPLES

    outlier_policy: OutlierPolicy = "mad"
    mad_threshold: float = 3.5
    """Number of MADs from the median to keep a sample."""

    iqr_factor: float = 1.5

    regression_threshold: float = DEFAULT_REGRESSION_THRESHOLD

    report_percentiles: tuple[float, ...] = DEFAULT_REPORT_PERCENTILES

    disable_gc_during_run: bool = True
    """Disable Python's cyclic GC while measuring so allocation
    spikes from cycle collection don't pollute timing samples."""

    isolate_per_benchmark: bool = True
    """Force a full GC + counter reset between benchmarks so one
    workload's tail allocations don't affect the next."""

    track_allocations: bool = False
    """When True, every sample also captures
    :func:`tracemalloc.take_snapshot` deltas — slows the run."""

    deterministic_seed: int = 0xA5_BE_F7
    """Seed used for the synthetic workloads' random number streams."""

    fail_on_regression: bool = False
    """When True, the suite returns a nonzero exit code on regression.
    Off by default — informative, not enforcing — until baselines
    are established."""

    extras: dict[str, str] = field(default_factory=dict)
    """Free-form notes for downstream tooling."""

    def __post_init__(self) -> None:
        if self.warmup_iterations < 0:
            raise ValueError("warmup_iterations must be >= 0")
        if self.measured_iterations < 1:
            raise ValueError("measured_iterations must be >= 1")
        if self.min_samples < 1:
            raise ValueError("min_samples must be >= 1")
        if not (0.0 < self.regression_threshold < 10.0):
            raise ValueError(
                f"regression_threshold {self.regression_threshold} "
                "must be in (0, 10)",
            )
        if self.outlier_policy == "mad" and self.mad_threshold <= 0:
            raise ValueError("mad_threshold must be > 0")
        if self.outlier_policy == "iqr" and self.iqr_factor <= 0:
            raise ValueError("iqr_factor must be > 0")


def default_config() -> BenchmarkConfig:
    return BenchmarkConfig()


def quick_config() -> BenchmarkConfig:
    """Faster config for smoke tests + CI sanity runs."""
    return BenchmarkConfig(
        warmup_iterations=10,
        measured_iterations=50,
        min_samples=10,
    )
