"""Synthetic runtime event workload.

Generates plausible runtime-event payloads with deterministic
priorities + types so backpressure / sampling / streaming layers
can be stressed without standing up the real instrumentation.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from asyncviz.stress.utils.deterministic_rng import DeterministicRng

_DEFAULT_EVENT_TYPES = (
    "asyncio.task.created",
    "asyncio.task.completed",
    "asyncio.task.cancelled",
    "asyncio.queue.metrics.updated",
    "runtime.metric",
    "runtime.warning",
    "asyncio.gather.completed",
)


@dataclass(frozen=True, slots=True)
class SyntheticEvent:
    sequence: int
    event_type: str
    task_id: str
    payload_bytes: int
    priority: int


def generate_event_storm(
    *,
    size: int,
    seed: int,
    payload_min: int = 64,
    payload_max: int = 1024,
    event_types: tuple[str, ...] = _DEFAULT_EVENT_TYPES,
) -> Iterator[SyntheticEvent]:
    """Yield ``size`` deterministic events."""
    if size < 0:
        raise ValueError(f"size must be >= 0 (got {size})")
    if payload_min < 0 or payload_max < payload_min:
        raise ValueError("invalid payload bounds")
    if not event_types:
        raise ValueError("event_types must be non-empty")
    rng = DeterministicRng(seed)
    types = tuple(event_types)
    for sequence in range(size):
        event_type = rng.choice(types)
        priority = _priority_for(event_type)
        payload_bytes = rng.integer(payload_min, payload_max)
        task_id = f"task-{rng.integer(0, max(1, size // 8) - 1):08d}"
        yield SyntheticEvent(
            sequence=sequence,
            event_type=event_type,
            task_id=task_id,
            payload_bytes=payload_bytes,
            priority=priority,
        )


def _priority_for(event_type: str) -> int:
    if event_type == "runtime.warning":
        return 3
    if event_type.startswith("asyncio.task."):
        return 2
    if event_type == "asyncio.gather.completed":
        return 2
    if event_type.endswith(".metrics.updated"):
        return 0
    if event_type == "runtime.metric":
        return 0
    return 1
