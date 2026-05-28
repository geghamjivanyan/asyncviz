"""Canonical benchmark value types.

* :class:`BenchmarkSpec` — what to run + how. Registered in the
  registry; produced by the decorator API.
* :class:`BenchmarkSample` — one measured iteration.
* :class:`BenchmarkResult` — aggregate statistics for one spec.
* :class:`BenchmarkSuiteResult` — collection of results from a run.

All are frozen dataclasses so they're cheap to pass around + safe
to hash into tracking sets.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

BenchmarkCategory = Literal[
    "instrumentation",
    "runtime",
    "replay",
    "websocket",
    "rendering",
    "memory",
    "stress",
    "synthetic",
]

BenchmarkKind = Literal["sync", "async"]


SyncBenchmarkFn = Callable[[], Any]
"""Synchronous benchmark — returns anything; return value is ignored."""

AsyncBenchmarkFn = Callable[[], Any]
"""Async benchmark — returns an awaitable that the runner awaits."""

SetupFn = Callable[[], Any]
"""Per-benchmark setup hook (returns an opaque token the teardown
receives back). Optional."""

TeardownFn = Callable[[Any], None]


@dataclass(frozen=True, slots=True)
class BenchmarkSpec:
    """Immutable benchmark descriptor."""

    name: str
    """Globally unique name. Convention: ``<category>.<scope>.<verb>``."""

    category: BenchmarkCategory
    kind: BenchmarkKind
    fn: SyncBenchmarkFn | AsyncBenchmarkFn
    description: str = ""

    measured_iterations: int = 0
    """``0`` means "use the runner's default"."""

    warmup_iterations: int = 0
    """``0`` means "use the runner's default"."""

    regression_threshold: float = 0.0
    """``0.0`` means "use the runner's default"."""

    setup: SetupFn | None = None
    teardown: TeardownFn | None = None

    metadata: dict[str, str] = field(default_factory=dict)
    """Free-form key/value tags surfaced in reports."""

    expected_max_p95_ns: int = 0
    """Soft assertion — when nonzero, the runner flags the
    benchmark as ``slow`` if its p95 exceeds this. Doesn't fail the
    run."""

    def with_metadata(self, **extras: str) -> BenchmarkSpec:
        """Return a copy with additional metadata merged in."""
        merged = {**self.metadata, **extras}
        return BenchmarkSpec(
            name=self.name,
            category=self.category,
            kind=self.kind,
            fn=self.fn,
            description=self.description,
            measured_iterations=self.measured_iterations,
            warmup_iterations=self.warmup_iterations,
            regression_threshold=self.regression_threshold,
            setup=self.setup,
            teardown=self.teardown,
            metadata=merged,
            expected_max_p95_ns=self.expected_max_p95_ns,
        )


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    """One measured iteration."""

    duration_ns: int
    allocations_delta_bytes: int = 0


@dataclass(frozen=True, slots=True)
class BenchmarkStatistics:
    """Aggregated statistics for one spec's samples."""

    sample_count: int
    samples_excluded: int
    median_ns: int
    mean_ns: int
    min_ns: int
    max_ns: int
    stdev_ns: int
    p95_ns: int
    p99_ns: int
    coefficient_of_variation: float
    """``stdev / mean`` — dimensionless noise metric. <0.05 is very
    stable; >0.2 suggests the workload itself has variance the
    benchmark can't smooth out."""

    cumulative_allocations_bytes: int = 0
    max_allocation_delta_bytes: int = 0


@dataclass(frozen=True, slots=True)
class BenchmarkOutcome:
    """One benchmark's final state."""

    spec_name: str
    category: BenchmarkCategory
    statistics: BenchmarkStatistics | None
    status: Literal["ok", "insufficient", "skipped", "failed", "slow"]
    error_detail: str = ""
    started_at_ns: int = 0
    ended_at_ns: int = 0
    iterations_run: int = 0
    warmup_iterations_run: int = 0

    @property
    def duration_wall_ns(self) -> int:
        return max(0, self.ended_at_ns - self.started_at_ns)


@dataclass(frozen=True, slots=True)
class BaselineComparison:
    """One benchmark's verdict against a baseline."""

    spec_name: str
    baseline_p95_ns: int
    current_p95_ns: int
    delta_ratio: float
    """``(current - baseline) / baseline`` — negative when faster."""
    threshold: float
    verdict: Literal["improved", "stable", "regressed", "no_baseline"]


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Per-benchmark result + optional baseline comparison."""

    outcome: BenchmarkOutcome
    comparison: BaselineComparison | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkEnvironment:
    """Captured environment for reproducibility."""

    python_version: str
    platform: str
    asyncio_loop: str
    asyncviz_version: str
    cpu_count: int
    benchmark_config_summary: dict[str, str] = field(default_factory=dict)
    captured_at_wall_ns: int = field(default_factory=time.time_ns)


@dataclass(frozen=True, slots=True)
class BenchmarkSuiteResult:
    """Output of one suite run."""

    environment: BenchmarkEnvironment
    results: tuple[BenchmarkResult, ...]
    started_at_ns: int
    ended_at_ns: int
    notes: dict[str, str] = field(default_factory=dict)

    @property
    def duration_wall_ns(self) -> int:
        return max(0, self.ended_at_ns - self.started_at_ns)

    @property
    def regressed(self) -> tuple[BenchmarkResult, ...]:
        return tuple(
            r for r in self.results
            if r.comparison is not None and r.comparison.verdict == "regressed"
        )

    @property
    def failures(self) -> tuple[BenchmarkResult, ...]:
        return tuple(
            r for r in self.results
            if r.outcome.status in ("failed", "insufficient")
        )
