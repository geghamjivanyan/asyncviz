"""Deterministic runtime-event streams.

Returns plain tuples of pre-built :class:`RuntimeEvent` instances so
benchmarks can iterate them without paying for per-iteration
construction. Determinism comes from a fixed seed + fixed counter
ordering — no wall-clock dependency.
"""

from __future__ import annotations

from asyncviz.runtime.events.models import (
    RuntimeEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
)


def build_task_event_stream(count: int) -> tuple[RuntimeEvent, ...]:
    """Build a (TaskCreated, TaskCompleted) pair for each task."""
    events: list[RuntimeEvent] = []
    for i in range(count):
        events.append(
            TaskCreatedEvent(task_id=f"t-{i}", task_name=f"n-{i}"),
        )
        events.append(
            TaskCompletedEvent(task_id=f"t-{i}", task_name=f"n-{i}"),
        )
    return tuple(events)
