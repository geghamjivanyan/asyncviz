"""Active-span tracking — the engine's mutable working set."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class OpenSegment:
    """A segment whose end has not yet been observed.

    Updated in-place by the engine until the corresponding close transition
    arrives. Converted to an immutable :class:`TimelineSegment` at that point.
    """

    task_id: str
    segment_id: str
    segment_type: str  # "run" | "wait"
    sequence_start: int | None
    monotonic_start_ns: int
    wall_start: float
    state: str
    parent_task_id: str | None = None
    coroutine_name: str | None = None
    task_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskTimelineState:
    """Per-task mutable working set tracked by the engine.

    Holds every finalized segment plus (at most one) open segment plus the
    lifecycle bookkeeping needed to fold this into a :class:`LifecycleSpan`
    on snapshot.

    Mutated only by the engine under its own lock.
    """

    task_id: str
    parent_task_id: str | None = None
    coroutine_name: str | None = None
    task_name: str | None = None
    created: bool = False
    created_at_monotonic_ns: int = 0
    created_at_wall: float = 0.0
    terminated_at_monotonic_ns: int | None = None
    terminated_at_wall: float | None = None
    terminal_state: str | None = None
    open_segment: OpenSegment | None = None
    segments: list = field(default_factory=list)  # list[TimelineSegment]
    segment_counter: int = 0
    run_duration_ns: int = 0
    wait_duration_ns: int = 0
    depth: int = 0
    root_task_id: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.terminal_state is not None

    def next_segment_id(self) -> str:
        """Deterministic segment id within this task — fine for replay round-trips."""
        index = self.segment_counter
        self.segment_counter += 1
        return f"{self.task_id}:{index}"
