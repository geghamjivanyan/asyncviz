"""EventBus publish + subscribe roundtrip overhead."""

from __future__ import annotations

from asyncviz.benchmarks.benchmark_registry import benchmark
from asyncviz.benchmarks.synthetic import build_task_event_stream
from asyncviz.runtime.events import EventBus

_EVENTS = build_task_event_stream(count=64)


def _drain(_bus: EventBus, event) -> None:  # type: ignore[no-untyped-def]
    pass


def _build_bus_with_one_subscriber() -> EventBus:
    bus = EventBus()
    bus.subscribe(lambda e: _drain(bus, e))
    return bus


@benchmark(
    name="instrumentation.event_bus.publish",
    category="instrumentation",
    description="EventBus.publish for 64 task events through 1 subscriber",
)
async def bench_event_bus_publish() -> None:
    bus = _build_bus_with_one_subscriber()
    await bus.start()
    try:
        for event in _EVENTS:
            bus.publish(event)
        await bus.join()
    finally:
        await bus.stop()
