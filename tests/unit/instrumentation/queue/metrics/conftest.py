from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.queue.metrics import (
    DEFAULT_QUEUE_METRICS_CONFIG,
    QueueMetricsConfig,
    QueueMetricsEngine,
    reset_queue_metrics_engine_metrics,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_tracing import (
    clear_queue_metrics_trace,
    set_queue_metrics_trace_enabled,
)
from asyncviz.runtime.events import EventBus


@pytest.fixture(autouse=True)
def _reset_engine_globals() -> Iterator[None]:
    reset_queue_metrics_engine_metrics()
    clear_queue_metrics_trace()
    set_queue_metrics_trace_enabled(False)
    yield
    reset_queue_metrics_engine_metrics()
    clear_queue_metrics_trace()
    set_queue_metrics_trace_enabled(False)


@pytest_asyncio.fixture
async def bus() -> AsyncIterator[EventBus]:
    bus = EventBus()
    await bus.start()
    try:
        yield bus
    finally:
        await bus.stop()


@pytest.fixture
def fast_emit_config() -> QueueMetricsConfig:
    """Force every event to immediately re-emit so tests don't have to wait
    on the debounce window."""
    return QueueMetricsConfig(
        updated_min_interval_seconds=0.0,
        updated_min_event_delta=1,
    )


@pytest.fixture
def engine_unbound(fast_emit_config: QueueMetricsConfig) -> QueueMetricsEngine:
    """An engine with no bus — for unit tests that drive ``apply_event``
    directly. Stable + deterministic."""
    return QueueMetricsEngine(bus=None, config=fast_emit_config)


@pytest.fixture
def default_config() -> QueueMetricsConfig:
    return DEFAULT_QUEUE_METRICS_CONFIG
