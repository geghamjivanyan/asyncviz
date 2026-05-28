"""Per-event allocation cost.

Pairs with ``track_allocations=True`` to report bytes-per-event.
"""

from __future__ import annotations

from asyncviz.benchmarks.benchmark_registry import benchmark
from asyncviz.runtime.events.models import TaskCreatedEvent


@benchmark(
    name="memory.event.construct_task_created",
    category="memory",
    description="Construct one TaskCreatedEvent (allocations tracked when enabled)",
)
def bench_construct_task_event() -> None:
    TaskCreatedEvent(task_id="t-alloc", task_name="alloc")
