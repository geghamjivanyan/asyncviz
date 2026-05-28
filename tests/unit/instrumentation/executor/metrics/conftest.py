from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.executor.metrics import (
    DEFAULT_EXECUTOR_METRICS_CONFIG,
    ExecutorMetricsConfig,
    ExecutorMetricsEngine,
    reset_executor_metrics_engine_metrics,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_tracing import (
    clear_executor_metrics_trace,
    set_executor_metrics_trace_enabled,
)
from asyncviz.runtime.events import EventBus


@pytest.fixture(autouse=True)
def _reset_engine_globals() -> Iterator[None]:
    reset_executor_metrics_engine_metrics()
    clear_executor_metrics_trace()
    set_executor_metrics_trace_enabled(False)
    yield
    reset_executor_metrics_engine_metrics()
    clear_executor_metrics_trace()
    set_executor_metrics_trace_enabled(False)


@pytest_asyncio.fixture
async def bus() -> AsyncIterator[EventBus]:
    bus = EventBus()
    await bus.start()
    try:
        yield bus
    finally:
        await bus.stop()


@pytest.fixture
def fast_emit_config() -> ExecutorMetricsConfig:
    """Force every event to immediately re-emit so tests don't wait
    on the debounce window."""
    return ExecutorMetricsConfig(
        updated_min_interval_seconds=0.0,
        updated_min_event_delta=1,
    )


@pytest.fixture
def engine_unbound(fast_emit_config: ExecutorMetricsConfig) -> ExecutorMetricsEngine:
    """An engine with no bus — for unit tests that drive ``apply_event``
    directly."""
    return ExecutorMetricsEngine(bus=None, config=fast_emit_config)


@pytest.fixture
def default_config() -> ExecutorMetricsConfig:
    return DEFAULT_EXECUTOR_METRICS_CONFIG
