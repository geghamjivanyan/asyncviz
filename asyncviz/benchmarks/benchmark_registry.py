"""Decorator-driven benchmark registry.

Benchmarks register themselves at import time via :func:`benchmark`:

    from asyncviz.benchmarks import benchmark

    @benchmark(name="instrumentation.task.create", category="instrumentation")
    async def bench_task_create() -> None:
        for _ in range(1000):
            ...

The registry is process-wide. Tests use :func:`reset_registry` to
isolate.
"""

from __future__ import annotations

import inspect
import threading
from collections.abc import Callable

from asyncviz.benchmarks.benchmark_models import (
    AsyncBenchmarkFn,
    BenchmarkCategory,
    BenchmarkKind,
    BenchmarkSpec,
    SetupFn,
    SyncBenchmarkFn,
    TeardownFn,
)


class _Registry:
    __slots__ = ("_lock", "_specs")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._specs: dict[str, BenchmarkSpec] = {}

    def register(self, spec: BenchmarkSpec) -> None:
        with self._lock:
            if spec.name in self._specs:
                raise ValueError(f"benchmark already registered: {spec.name}")
            self._specs[spec.name] = spec

    def unregister(self, name: str) -> None:
        with self._lock:
            self._specs.pop(name, None)

    def get(self, name: str) -> BenchmarkSpec | None:
        with self._lock:
            return self._specs.get(name)

    def all(self) -> tuple[BenchmarkSpec, ...]:
        with self._lock:
            return tuple(sorted(self._specs.values(), key=lambda s: s.name))

    def filtered(
        self,
        *,
        category: BenchmarkCategory | None = None,
        name_prefix: str | None = None,
    ) -> tuple[BenchmarkSpec, ...]:
        with self._lock:
            specs = list(self._specs.values())
        if category is not None:
            specs = [s for s in specs if s.category == category]
        if name_prefix is not None:
            specs = [s for s in specs if s.name.startswith(name_prefix)]
        return tuple(sorted(specs, key=lambda s: s.name))

    def clear(self) -> None:
        with self._lock:
            self._specs.clear()


_REGISTRY: _Registry = _Registry()


def get_registry() -> _Registry:
    return _REGISTRY


def reset_registry() -> None:
    _REGISTRY.clear()


# ── decorator API ─────────────────────────────────────────────────


def benchmark(
    *,
    name: str,
    category: BenchmarkCategory,
    description: str = "",
    measured_iterations: int = 0,
    warmup_iterations: int = 0,
    regression_threshold: float = 0.0,
    setup: SetupFn | None = None,
    teardown: TeardownFn | None = None,
    expected_max_p95_ns: int = 0,
    metadata: dict[str, str] | None = None,
) -> Callable[
    [SyncBenchmarkFn | AsyncBenchmarkFn],
    SyncBenchmarkFn | AsyncBenchmarkFn,
]:
    """Decorator that registers a benchmark with the global registry."""

    def _decorator(
        fn: SyncBenchmarkFn | AsyncBenchmarkFn,
    ) -> SyncBenchmarkFn | AsyncBenchmarkFn:
        kind: BenchmarkKind = (
            "async" if inspect.iscoroutinefunction(fn) else "sync"
        )
        spec = BenchmarkSpec(
            name=name,
            category=category,
            kind=kind,
            fn=fn,
            description=description or (fn.__doc__ or "").strip().splitlines()[0]
            if fn.__doc__ else "",
            measured_iterations=measured_iterations,
            warmup_iterations=warmup_iterations,
            regression_threshold=regression_threshold,
            setup=setup,
            teardown=teardown,
            metadata=dict(metadata or {}),
            expected_max_p95_ns=expected_max_p95_ns,
        )
        _REGISTRY.register(spec)
        return fn

    return _decorator
