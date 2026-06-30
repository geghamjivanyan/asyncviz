"""Registry + runner tests."""

from __future__ import annotations

import pytest

from asyncviz.benchmarks import (
    BenchmarkConfig,
    BenchmarkRunner,
    benchmark,
    get_registry,
    quick_config,
    run_all,
)


def test_decorator_registers_sync_benchmark() -> None:
    @benchmark(name="test.sync.add", category="synthetic")
    def bench_add() -> None:
        _ = 1 + 1

    specs = get_registry().all()
    assert len(specs) == 1
    assert specs[0].kind == "sync"
    assert specs[0].name == "test.sync.add"


def test_decorator_registers_async_benchmark() -> None:
    @benchmark(name="test.async.noop", category="synthetic")
    async def bench_noop() -> None:
        return None

    specs = get_registry().all()
    assert specs[0].kind == "async"


def test_duplicate_registration_raises() -> None:
    @benchmark(name="test.dup", category="synthetic")
    def first() -> None:
        return None

    with pytest.raises(ValueError, match="already registered"):

        @benchmark(name="test.dup", category="synthetic")
        def second() -> None:
            return None


def test_runner_executes_sync_benchmark() -> None:
    counter = [0]

    @benchmark(name="test.sync.counter", category="synthetic")
    def bench_counter() -> None:
        counter[0] += 1

    runner = BenchmarkRunner(config=quick_config())
    spec = get_registry().get("test.sync.counter")
    assert spec is not None
    result = runner.run_benchmark(spec)
    assert result.outcome.status == "ok"
    assert result.outcome.statistics is not None
    assert result.outcome.statistics.sample_count >= 10
    # warmup + measured.
    assert counter[0] >= 60


def test_runner_executes_async_benchmark() -> None:
    counter = [0]

    @benchmark(name="test.async.counter", category="synthetic")
    async def bench_async() -> None:
        counter[0] += 1

    runner = BenchmarkRunner(config=quick_config())
    spec = get_registry().get("test.async.counter")
    assert spec is not None
    result = runner.run_benchmark(spec)
    assert result.outcome.status == "ok"
    assert counter[0] >= 60


def test_runner_surfaces_failure_detail() -> None:
    @benchmark(name="test.fail", category="synthetic")
    def bench_fail() -> None:
        raise RuntimeError("kaboom")

    runner = BenchmarkRunner(config=quick_config())
    spec = get_registry().get("test.fail")
    assert spec is not None
    result = runner.run_benchmark(spec)
    assert result.outcome.status == "failed"
    assert "kaboom" in result.outcome.error_detail


def test_runner_runs_setup_and_teardown() -> None:
    tokens: list = []

    def setup():
        tokens.append("setup")
        return "token"

    def teardown(value):
        tokens.append(f"teardown:{value}")

    @benchmark(
        name="test.setup_teardown",
        category="synthetic",
        setup=setup,
        teardown=teardown,
    )
    def bench() -> None:
        return None

    spec = get_registry().get("test.setup_teardown")
    assert spec is not None
    runner = BenchmarkRunner(config=quick_config())
    runner.run_benchmark(spec)
    assert "setup" in tokens
    assert "teardown:token" in tokens


def test_suite_runs_all_filtered_specs() -> None:
    @benchmark(name="test.a", category="synthetic")
    def a() -> None:
        return None

    @benchmark(name="test.b", category="synthetic")
    def b() -> None:
        return None

    @benchmark(name="other.c", category="runtime")
    def c() -> None:
        return None

    suite = run_all(config=quick_config(), name_prefix="test.")
    names = {r.outcome.spec_name for r in suite.results}
    assert names == {"test.a", "test.b"}


def test_suite_filters_by_category() -> None:
    @benchmark(name="test.a", category="synthetic")
    def a() -> None:
        return None

    @benchmark(name="other.b", category="runtime")
    def b() -> None:
        return None

    suite = run_all(config=quick_config(), category="synthetic")
    names = {r.outcome.spec_name for r in suite.results}
    assert names == {"test.a"}


def test_insufficient_samples_marked() -> None:
    @benchmark(
        name="test.too_few",
        category="synthetic",
        warmup_iterations=0,
        measured_iterations=1,
    )
    def bench() -> None:
        return None

    spec = get_registry().get("test.too_few")
    assert spec is not None
    cfg = BenchmarkConfig(
        warmup_iterations=0,
        measured_iterations=1,
        min_samples=10,
    )
    runner = BenchmarkRunner(config=cfg)
    result = runner.run_benchmark(spec)
    assert result.outcome.status == "insufficient"
