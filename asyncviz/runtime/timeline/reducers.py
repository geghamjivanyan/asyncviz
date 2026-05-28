"""Per-intent reducers — apply one transition to the engine's working set.

Each reducer takes a :class:`TaskTimelineState`, the transition timing,
and returns a structured :class:`TimelineReducerResult` describing what it
did. The engine uses the result to update metrics and emit notifications.

Reducers are pure with respect to ``state`` (and metrics, when threaded
through). They do not log, do not allocate beyond what they return, and
do not consult global state.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.timeline.lifecycle import (
    close_open_segment,
    finalize_task,
    open_new_segment,
)
from asyncviz.runtime.timeline.spans import TaskTimelineState


@dataclass(frozen=True, slots=True)
class TimelineReducerResult:
    """Outcome of one transition application."""

    applied: bool
    closed_a_segment: bool
    opened_segment_type: str | None
    finalized_task: bool
    reason: str | None = None
    invalid: bool = False

    @classmethod
    def rejected(
        cls,
        reason: str,
        *,
        invalid: bool = False,
    ) -> TimelineReducerResult:
        return cls(
            applied=False,
            closed_a_segment=False,
            opened_segment_type=None,
            finalized_task=False,
            reason=reason,
            invalid=invalid,
        )


def reduce_create(
    state: TaskTimelineState,
    *,
    sequence: int | None,
    monotonic_ns: int,
    wall_seconds: float,
    parent_task_id: str | None,
    coroutine_name: str | None,
    task_name: str | None,
    depth: int = 0,
    root_task_id: str | None = None,
) -> TimelineReducerResult:
    """Initialize a :class:`TaskTimelineState`.

    Idempotent: a second CREATE for the same task is rejected. The active
    span starts in a "created but not running" state — no open segment
    until a RUNNING transition arrives.
    """
    if state.created:
        return TimelineReducerResult.rejected(
            f"task {state.task_id!r} already created",
            invalid=True,
        )
    state.created = True
    state.created_at_monotonic_ns = monotonic_ns
    state.created_at_wall = wall_seconds
    state.parent_task_id = parent_task_id
    state.coroutine_name = coroutine_name
    state.task_name = task_name
    state.depth = depth
    state.root_task_id = root_task_id or state.task_id
    _ = sequence  # reserved for future per-task creation sequence logging
    return TimelineReducerResult(
        applied=True,
        closed_a_segment=False,
        opened_segment_type=None,
        finalized_task=False,
    )


def reduce_open_run(
    state: TaskTimelineState,
    *,
    sequence: int | None,
    monotonic_ns: int,
    wall_seconds: float,
) -> TimelineReducerResult:
    """Open a ``"run"`` segment.

    If a previous segment is open, close it first — that closure timestamp
    becomes the new segment's start, so the engine never leaves a gap on
    the timeline.
    """
    if state.terminal_state is not None:
        return TimelineReducerResult.rejected(
            f"task {state.task_id!r} already terminal in {state.terminal_state!r}",
            invalid=True,
        )
    if not state.created:
        return TimelineReducerResult.rejected(
            f"task {state.task_id!r} has no CREATED transition yet",
            invalid=True,
        )

    closed = close_open_segment(
        state,
        sequence_end=sequence,
        monotonic_end_ns=monotonic_ns,
        wall_end=wall_seconds,
    )
    open_new_segment(
        state,
        segment_type="run",
        sequence_start=sequence,
        monotonic_start_ns=monotonic_ns,
        wall_start=wall_seconds,
        target_state=TaskState.RUNNING,
    )
    return TimelineReducerResult(
        applied=True,
        closed_a_segment=closed,
        opened_segment_type="run",
        finalized_task=False,
    )


def reduce_open_wait(
    state: TaskTimelineState,
    *,
    sequence: int | None,
    monotonic_ns: int,
    wall_seconds: float,
) -> TimelineReducerResult:
    """Open a ``"wait"`` segment (closes any open run/wait first)."""
    if state.terminal_state is not None:
        return TimelineReducerResult.rejected(
            f"task {state.task_id!r} already terminal in {state.terminal_state!r}",
            invalid=True,
        )
    if not state.created:
        return TimelineReducerResult.rejected(
            f"task {state.task_id!r} has no CREATED transition yet",
            invalid=True,
        )

    closed = close_open_segment(
        state,
        sequence_end=sequence,
        monotonic_end_ns=monotonic_ns,
        wall_end=wall_seconds,
    )
    open_new_segment(
        state,
        segment_type="wait",
        sequence_start=sequence,
        monotonic_start_ns=monotonic_ns,
        wall_start=wall_seconds,
        target_state=TaskState.WAITING,
    )
    return TimelineReducerResult(
        applied=True,
        closed_a_segment=closed,
        opened_segment_type="wait",
        finalized_task=False,
    )


def reduce_close_and_finalize(
    state: TaskTimelineState,
    *,
    target_state: TaskState,
    sequence: int | None,
    monotonic_ns: int,
    wall_seconds: float,
) -> TimelineReducerResult:
    """Close any open segment and mark the task terminal.

    A second terminal transition is a no-op — the first one wins, matching
    the state-store's terminal-stickiness invariant.
    """
    if state.terminal_state is not None:
        return TimelineReducerResult.rejected(
            f"task {state.task_id!r} already terminal in {state.terminal_state!r}",
            invalid=True,
        )
    closed = close_open_segment(
        state,
        sequence_end=sequence,
        monotonic_end_ns=monotonic_ns,
        wall_end=wall_seconds,
    )
    finalize_task(
        state,
        terminal_state=target_state,
        monotonic_end_ns=monotonic_ns,
        wall_end=wall_seconds,
    )
    return TimelineReducerResult(
        applied=True,
        closed_a_segment=closed,
        opened_segment_type=None,
        finalized_task=True,
    )
