from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.queue import (
    QueueInstrumentationEngine,
    QueueRegistry,
    get_default_queue_registry,
    reset_default_queue_registry,
    reset_queue_metrics,
)
from asyncviz.instrumentation.queue.queue_tracing import (
    clear_queue_trace,
    set_queue_trace_enabled,
)
from asyncviz.runtime.events import EventBus


@pytest.fixture(autouse=True)
def _reset_queue_globals() -> Iterator[None]:
    """Ensure each test sees a clean default registry, metrics, and trace ring."""
    reset_default_queue_registry()
    reset_queue_metrics()
    clear_queue_trace()
    set_queue_trace_enabled(False)
    yield
    reset_default_queue_registry()
    reset_queue_metrics()
    clear_queue_trace()
    set_queue_trace_enabled(False)


@pytest.fixture
def registry() -> QueueRegistry:
    return get_default_queue_registry()


@pytest_asyncio.fixture
async def bus() -> AsyncIterator[EventBus]:
    bus = EventBus()
    await bus.start()
    try:
        yield bus
    finally:
        await bus.stop()


@pytest.fixture
def engine_unpatched(bus: EventBus) -> Iterator[QueueInstrumentationEngine]:
    """An engine bound to the bus but not yet patched.

    The test owns when to call ``patch()`` / ``unpatch()`` — keeps the
    test responsible for restoring stdlib state if the assertion fails
    halfway through.
    """
    engine = QueueInstrumentationEngine(bus=bus)
    try:
        yield engine
    finally:
        if engine.is_patched:
            engine.unpatch()


@pytest_asyncio.fixture
async def engine(
    engine_unpatched: QueueInstrumentationEngine,
) -> AsyncIterator[QueueInstrumentationEngine]:
    """Engine that's actively patched for the duration of the test."""
    engine_unpatched.patch()
    yield engine_unpatched
    engine_unpatched.unpatch()
