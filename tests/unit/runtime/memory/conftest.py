"""Shared fixtures for memory-optimizer tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.memory import (
    EventMemoryOptimizer,
    MemoryOptimizerConfig,
    clear_memory_trace,
    reset_global_interner,
    reset_global_optimizer,
    reset_memory_metrics,
    set_memory_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_memory_globals() -> None:
    reset_memory_metrics()
    clear_memory_trace()
    set_memory_trace_enabled(False)
    reset_global_interner()
    reset_global_optimizer()


@pytest.fixture
def optimizer() -> EventMemoryOptimizer:
    return EventMemoryOptimizer(config=MemoryOptimizerConfig())
