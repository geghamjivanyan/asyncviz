"""Typed metadata records for instrumented ``asyncio.gather`` calls.

Kept separate from the registry so the dataclasses don't drag a
``weakref`` import into modules that just want to render diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GatherIdentity:
    """Stable identity record for one instrumented gather call."""

    gather_id: str
    """Monotonic ``g-N`` id allocated by the registry."""

    parent_task_id: str | None
    """Runtime task id of the awaiter at gather-invocation time.
    ``None`` when ``gather`` is called from non-task contexts."""

    child_task_ids: tuple[str, ...]
    """Resolved task ids for every child the gather waits on.
    Order matches the positional argument order, which is also the
    order gather returns its results in."""

    child_count: int
    return_exceptions: bool
    created_at_ns: int


@dataclass(frozen=True, slots=True)
class GatherSnapshot:
    """Frozen view of a gather's progress at event time."""

    gather_id: str
    parent_task_id: str | None
    child_count: int
    completed_count: int
    """Number of children that have transitioned to done so far.
    Always ``<= child_count``."""

    pending_count: int
    """``child_count - completed_count``; redundant but cheap to read on
    the wire."""

    cancelled: bool
    failed: bool
    return_exceptions: bool
