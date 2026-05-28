"""Shared fixtures for benchmark-infrastructure tests."""

from __future__ import annotations

import pytest

from asyncviz.benchmarks import (
    clear_benchmark_trace,
    reset_benchmark_metrics,
    reset_registry,
    set_benchmark_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_benchmark_globals() -> None:
    reset_registry()
    reset_benchmark_metrics()
    clear_benchmark_trace()
    set_benchmark_trace_enabled(False)
