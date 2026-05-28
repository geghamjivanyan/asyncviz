"""High-volume event storm.

Pushes 5k events through a bus + a single subscriber to validate
the bus stays linear under bursty load.
"""

from __future__ import annotations

from asyncviz.benchmarks.benchmark_registry import benchmark
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models import TaskCreatedEvent

_EVENT_COUNT = 5_000


@benchmark(
    name="stress.event_bus.5k_storm",
    category="stress",
    description="EventBus.publish for 5,000 task events through 1 subscriber",
    warmup_iterations=2,
    measured_iterations=10,
)
async def bench_event_storm() -> None:
    bus = EventBus()
    bus.subscribe(lambda _e: None)
    await bus.start()
    try:
        for i in range(_EVENT_COUNT):
            bus.publish(TaskCreatedEvent(task_id=f"t-{i}", task_name=f"n-{i}"))
        await bus.join()
    finally:
        await bus.stop()
