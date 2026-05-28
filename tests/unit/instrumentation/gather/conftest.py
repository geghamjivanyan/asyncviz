from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.gather import (
    GatherInstrumentationEngine,
    GatherRegistry,
    get_default_gather_registry,
    reset_default_gather_registry,
    reset_gather_metrics,
)
from asyncviz.instrumentation.gather.gather_tracing import (
    clear_gather_trace,
    set_gather_trace_enabled,
)
from asyncviz.runtime.events import EventBus


@pytest.fixture(autouse=True)
def _reset_gather_globals() -> Iterator[None]:
    reset_default_gather_registry()
    reset_gather_metrics()
    clear_gather_trace()
    set_gather_trace_enabled(False)
    yield
    reset_default_gather_registry()
    reset_gather_metrics()
    clear_gather_trace()
    set_gather_trace_enabled(False)


@pytest.fixture
def registry() -> GatherRegistry:
    return get_default_gather_registry()


@pytest_asyncio.fixture
async def bus() -> AsyncIterator[EventBus]:
    bus = EventBus()
    await bus.start()
    try:
        yield bus
    finally:
        await bus.stop()


@pytest.fixture
def engine_unpatched(bus: EventBus) -> Iterator[GatherInstrumentationEngine]:
    engine = GatherInstrumentationEngine(bus=bus)
    try:
        yield engine
    finally:
        if engine.is_patched:
            engine.unpatch()


@pytest_asyncio.fixture
async def engine(
    engine_unpatched: GatherInstrumentationEngine,
) -> AsyncIterator[GatherInstrumentationEngine]:
    engine_unpatched.patch()
    yield engine_unpatched
    engine_unpatched.unpatch()
