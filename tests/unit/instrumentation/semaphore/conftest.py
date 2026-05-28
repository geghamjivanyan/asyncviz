from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.semaphore import (
    SemaphoreInstrumentationEngine,
    SemaphoreRegistry,
    get_default_semaphore_registry,
    reset_default_semaphore_registry,
    reset_semaphore_metrics,
)
from asyncviz.instrumentation.semaphore.semaphore_tracing import (
    clear_semaphore_trace,
    set_semaphore_trace_enabled,
)
from asyncviz.runtime.events import EventBus


@pytest.fixture(autouse=True)
def _reset_semaphore_globals() -> Iterator[None]:
    reset_default_semaphore_registry()
    reset_semaphore_metrics()
    clear_semaphore_trace()
    set_semaphore_trace_enabled(False)
    yield
    reset_default_semaphore_registry()
    reset_semaphore_metrics()
    clear_semaphore_trace()
    set_semaphore_trace_enabled(False)


@pytest.fixture
def registry() -> SemaphoreRegistry:
    return get_default_semaphore_registry()


@pytest_asyncio.fixture
async def bus() -> AsyncIterator[EventBus]:
    bus = EventBus()
    await bus.start()
    try:
        yield bus
    finally:
        await bus.stop()


@pytest.fixture
def engine_unpatched(bus: EventBus) -> Iterator[SemaphoreInstrumentationEngine]:
    engine = SemaphoreInstrumentationEngine(bus=bus)
    try:
        yield engine
    finally:
        if engine.is_patched:
            engine.unpatch()


@pytest_asyncio.fixture
async def engine(
    engine_unpatched: SemaphoreInstrumentationEngine,
) -> AsyncIterator[SemaphoreInstrumentationEngine]:
    engine_unpatched.patch()
    yield engine_unpatched
    engine_unpatched.unpatch()
