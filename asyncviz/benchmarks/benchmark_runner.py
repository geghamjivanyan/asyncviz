"""Canonical benchmark runner.

Orchestrates warmup, measurement, statistics, and (optional)
baseline comparison for one or more :class:`BenchmarkSpec`s.

Lifecycle for one benchmark:

1. Optional ``setup`` produces a token.
2. ``warmup_iterations`` warmup invocations (discarded).
3. ``measured_iterations`` measured invocations (timed individually).
4. Statistics aggregation.
5. Optional baseline comparison.
6. Optional ``teardown(token)``.

The runner enforces GC discipline + per-benchmark isolation. It is
deliberately *not* async itself — it dispatches async benchmarks
through ``asyncio.run`` (one event loop per benchmark, never reused)
so an async crash never leaks state into the next benchmark.
"""

from __future__ import annotations

import asyncio
import contextlib
import platform
import sys
import time
from collections.abc import Iterable

from asyncviz.benchmarks.benchmark_configuration import (
    BenchmarkConfig,
    default_config,
)
from asyncviz.benchmarks.benchmark_models import (
    BaselineComparison,
    BenchmarkEnvironment,
    BenchmarkOutcome,
    BenchmarkResult,
    BenchmarkSample,
    BenchmarkSpec,
    BenchmarkSuiteResult,
)
from asyncviz.benchmarks.benchmark_statistics import aggregate_samples
from asyncviz.benchmarks.utilities.gc_control import (
    force_gc_round,
    gc_disabled_during,
)
from asyncviz.benchmarks.utilities.memory import (
    capture_allocation_baseline,
    sample_allocation_delta,
    stop_tracing_if_active,
)


class BenchmarkRunner:
    """Runs one or more :class:`BenchmarkSpec`s end-to-end."""

    __slots__ = ("_baselines", "_config")

    def __init__(
        self,
        config: BenchmarkConfig | None = None,
        baselines: dict[str, int] | None = None,
    ) -> None:
        self._config = config or default_config()
        self._baselines = dict(baselines or {})

    @property
    def config(self) -> BenchmarkConfig:
        return self._config

    @property
    def baselines(self) -> dict[str, int]:
        return dict(self._baselines)

    def set_baselines(self, baselines: dict[str, int]) -> None:
        self._baselines = dict(baselines)

    # ── single-spec ───────────────────────────────────────────────

    def run_benchmark(self, spec: BenchmarkSpec) -> BenchmarkResult:
        """Run one spec end-to-end."""
        started_ns = time.perf_counter_ns()
        warmup_iters = spec.warmup_iterations or self._config.warmup_iterations
        measured_iters = spec.measured_iterations or self._config.measured_iterations

        token = None
        try:
            if spec.setup is not None:
                token = spec.setup()
        except Exception as exc:
            return _failure(spec, started_ns, f"setup failed: {exc}")

        samples: list[BenchmarkSample] = []
        try:
            if spec.kind == "sync":
                self._run_sync(spec, warmup_iters, measured_iters, samples)
            else:
                self._run_async(spec, warmup_iters, measured_iters, samples)
        except Exception as exc:
            ended_ns = time.perf_counter_ns()
            return BenchmarkResult(
                outcome=BenchmarkOutcome(
                    spec_name=spec.name,
                    category=spec.category,
                    statistics=None,
                    status="failed",
                    error_detail=str(exc),
                    started_at_ns=started_ns,
                    ended_at_ns=ended_ns,
                    iterations_run=len(samples),
                    warmup_iterations_run=warmup_iters,
                ),
            )
        finally:
            if spec.teardown is not None and token is not None:
                # Teardown failures shouldn't taint results.
                with contextlib.suppress(Exception):
                    spec.teardown(token)
            if self._config.isolate_per_benchmark:
                force_gc_round()
            if self._config.track_allocations:
                stop_tracing_if_active()

        statistics = aggregate_samples(
            samples,
            policy=self._config.outlier_policy,
            mad_threshold=self._config.mad_threshold,
            iqr_factor=self._config.iqr_factor,
        )
        ended_ns = time.perf_counter_ns()
        status: str = "ok"
        if statistics.sample_count < self._config.min_samples:
            status = "insufficient"
        elif spec.expected_max_p95_ns > 0 and statistics.p95_ns > spec.expected_max_p95_ns:
            status = "slow"
        outcome = BenchmarkOutcome(
            spec_name=spec.name,
            category=spec.category,
            statistics=statistics,
            status=status,  # type: ignore[arg-type]
            started_at_ns=started_ns,
            ended_at_ns=ended_ns,
            iterations_run=len(samples),
            warmup_iterations_run=warmup_iters,
        )
        comparison = self._compare_baseline(spec, statistics)
        return BenchmarkResult(outcome=outcome, comparison=comparison)

    # ── suite ─────────────────────────────────────────────────────

    def run_suite(
        self,
        specs: Iterable[BenchmarkSpec],
        *,
        notes: dict[str, str] | None = None,
    ) -> BenchmarkSuiteResult:
        started = time.perf_counter_ns()
        results: list[BenchmarkResult] = []
        for spec in specs:
            results.append(self.run_benchmark(spec))
        ended = time.perf_counter_ns()
        return BenchmarkSuiteResult(
            environment=self._capture_environment(),
            results=tuple(results),
            started_at_ns=started,
            ended_at_ns=ended,
            notes=dict(notes or {}),
        )

    # ── internals ─────────────────────────────────────────────────

    def _run_sync(
        self,
        spec: BenchmarkSpec,
        warmup_iters: int,
        measured_iters: int,
        samples: list[BenchmarkSample],
    ) -> None:
        # Warmup.
        fn = spec.fn
        for _ in range(warmup_iters):
            fn()  # type: ignore[misc]
        # Measurement loop.
        track_alloc = self._config.track_allocations
        with gc_disabled_during() if self._config.disable_gc_during_run else _nullctx():
            for _ in range(measured_iters):
                sample = self._timed_sync_call(fn, track_alloc=track_alloc)
                samples.append(sample)

    def _run_async(
        self,
        spec: BenchmarkSpec,
        warmup_iters: int,
        measured_iters: int,
        samples: list[BenchmarkSample],
    ) -> None:
        track_alloc = self._config.track_allocations

        async def _drive() -> None:
            fn = spec.fn
            for _ in range(warmup_iters):
                await fn()  # type: ignore[misc]
            for _ in range(measured_iters):
                sample = await self._timed_async_call(fn, track_alloc=track_alloc)
                samples.append(sample)

        # One loop per benchmark — never reused.
        loop = asyncio.new_event_loop()
        try:
            with gc_disabled_during() if self._config.disable_gc_during_run else _nullctx():
                loop.run_until_complete(_drive())
        finally:
            loop.close()

    @staticmethod
    def _timed_sync_call(fn, *, track_alloc: bool) -> BenchmarkSample:  # type: ignore[no-untyped-def]
        baseline = capture_allocation_baseline() if track_alloc else None
        started = time.perf_counter_ns()
        fn()
        elapsed = time.perf_counter_ns() - started
        delta = 0
        if track_alloc and baseline is not None:
            delta = sample_allocation_delta(baseline).delta_bytes
        return BenchmarkSample(duration_ns=elapsed, allocations_delta_bytes=delta)

    @staticmethod
    async def _timed_async_call(fn, *, track_alloc: bool) -> BenchmarkSample:  # type: ignore[no-untyped-def]
        baseline = capture_allocation_baseline() if track_alloc else None
        started = time.perf_counter_ns()
        await fn()
        elapsed = time.perf_counter_ns() - started
        delta = 0
        if track_alloc and baseline is not None:
            delta = sample_allocation_delta(baseline).delta_bytes
        return BenchmarkSample(duration_ns=elapsed, allocations_delta_bytes=delta)

    def _compare_baseline(
        self,
        spec: BenchmarkSpec,
        stats,  # type: ignore[no-untyped-def]
    ) -> BaselineComparison | None:
        baseline = self._baselines.get(spec.name)
        if baseline is None:
            return BaselineComparison(
                spec_name=spec.name,
                baseline_p95_ns=0,
                current_p95_ns=stats.p95_ns,
                delta_ratio=0.0,
                threshold=spec.regression_threshold or self._config.regression_threshold,
                verdict="no_baseline",
            )
        if baseline <= 0:
            return BaselineComparison(
                spec_name=spec.name,
                baseline_p95_ns=baseline,
                current_p95_ns=stats.p95_ns,
                delta_ratio=0.0,
                threshold=spec.regression_threshold or self._config.regression_threshold,
                verdict="no_baseline",
            )
        delta = (stats.p95_ns - baseline) / baseline
        threshold = spec.regression_threshold or self._config.regression_threshold
        if delta > threshold:
            verdict = "regressed"
        elif delta < -threshold:
            verdict = "improved"
        else:
            verdict = "stable"
        return BaselineComparison(
            spec_name=spec.name,
            baseline_p95_ns=baseline,
            current_p95_ns=stats.p95_ns,
            delta_ratio=delta,
            threshold=threshold,
            verdict=verdict,  # type: ignore[arg-type]
        )

    def _capture_environment(self) -> BenchmarkEnvironment:
        try:
            cpu_count = __import__("os").cpu_count() or 0
        except Exception:
            cpu_count = 0
        return BenchmarkEnvironment(
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            asyncio_loop=type(asyncio.new_event_loop()).__name__,
            asyncviz_version=_asyncviz_version(),
            cpu_count=cpu_count,
            benchmark_config_summary={
                "warmup_iterations": str(self._config.warmup_iterations),
                "measured_iterations": str(self._config.measured_iterations),
                "outlier_policy": self._config.outlier_policy,
                "regression_threshold": str(self._config.regression_threshold),
                "disable_gc_during_run": str(self._config.disable_gc_during_run),
                "track_allocations": str(self._config.track_allocations),
            },
        )


def _asyncviz_version() -> str:
    try:
        from asyncviz.packaging import package_version  # local import — avoid cycles

        return package_version()
    except Exception:
        return "unknown"


def _failure(
    spec: BenchmarkSpec,
    started_ns: int,
    detail: str,
) -> BenchmarkResult:
    ended_ns = time.perf_counter_ns()
    return BenchmarkResult(
        outcome=BenchmarkOutcome(
            spec_name=spec.name,
            category=spec.category,
            statistics=None,
            status="failed",
            error_detail=detail,
            started_at_ns=started_ns,
            ended_at_ns=ended_ns,
        ),
    )


class _NullCtx:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None


def _nullctx() -> _NullCtx:
    return _NullCtx()
