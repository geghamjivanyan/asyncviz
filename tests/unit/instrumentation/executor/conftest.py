from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.executor import (
    ExecutorInstrumentationEngine,
    reset_default_executor_registry,
    reset_default_work_item_registry,
    reset_executor_metrics,
)
from asyncviz.instrumentation.executor.executor_tracing import (
    clear_executor_trace,
    set_executor_trace_enabled,
)
from asyncviz.runtime.events import EventBus


@pytest.fixture(autouse=True)
def _reset_executor_globals() -> Iterator[None]:
    reset_default_executor_registry()
    reset_default_work_item_registry()
    reset_executor_metrics()
    clear_executor_trace()
    set_executor_trace_enabled(False)
    yield
    reset_default_executor_registry()
    reset_default_work_item_registry()
    reset_executor_metrics()
    clear_executor_trace()
    set_executor_trace_enabled(False)


@pytest_asyncio.fixture
async def bus() -> AsyncIterator[EventBus]:
    bus = EventBus()
    await bus.start()
    try:
        yield bus
    finally:
        await bus.stop()


@pytest.fixture
def engine_unpatched(bus: EventBus) -> Iterator[ExecutorInstrumentationEngine]:
    engine = ExecutorInstrumentationEngine(bus=bus)
    try:
        yield engine
    finally:
        if engine.is_patched:
            engine.unpatch()


@pytest_asyncio.fixture
async def engine(
    engine_unpatched: ExecutorInstrumentationEngine,
) -> AsyncIterator[ExecutorInstrumentationEngine]:
    engine_unpatched.patch()
    yield engine_unpatched
    engine_unpatched.unpatch()
