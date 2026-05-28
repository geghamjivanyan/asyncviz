"""Topology-aware sampling guardrails.

Even under heavy overload, the dependency graph + task-tree
reducers must see *every* structural mutation (task create/destroy,
edge add/remove). Dropping one of these corrupts the downstream
visualization — the dashboard would show a "ghost" task that never
finishes, or an orphaned subgraph.

This module is a tiny guardrail: a predicate that the websocket
controller can consult to enforce "structural events bypass the
sampler" even when no priority remapping is configured.
"""

from __future__ import annotations

from asyncviz.runtime.sampling.models.sampling_priority import (
    SamplingPriority,
    classify_event_priority,
)

STRUCTURAL_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "asyncio.task.created",
        "asyncio.task.completed",
        "asyncio.task.cancelled",
        "asyncio.task.failed",
        "asyncio.queue.created",
        "asyncio.queue.cancelled",
        "asyncio.semaphore.created",
        "asyncio.gather.created",
        "asyncio.gather.completed",
        "asyncio.gather.cancelled",
        "asyncio.gather.failed",
        "asyncio.gather.child.attached",
        "asyncio.executor.registered",
        "runtime.started",
        "runtime.stopped",
    },
)


def is_structural_event(event_type: str) -> bool:
    """Cheap structural-event check used by the websocket +
    recorder sampling paths."""
    if event_type in STRUCTURAL_EVENT_TYPES:
        return True
    priority = classify_event_priority(event_type)
    return priority in (SamplingPriority.STRUCTURAL, SamplingPriority.CRITICAL)


def force_retain_structural(event_type: str) -> SamplingPriority | None:
    """Returns the upgraded priority if the event must be retained,
    else None.

    Callers pass the result into ``sampler.evaluate(priority=...)``
    so the structural floor is honored even when an upstream tier
    would have dropped it."""
    if event_type in STRUCTURAL_EVENT_TYPES:
        return SamplingPriority.STRUCTURAL
    return None
