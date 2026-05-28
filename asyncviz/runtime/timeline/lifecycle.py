"""Shared transition → engine-state helpers.

The reducers in :mod:`asyncviz.runtime.timeline.reducers` are the canonical
mutators; this module holds the small pure routines they share.
"""

from __future__ import annotations

from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.timeline.segments import finalize_segment
from asyncviz.runtime.timeline.spans import OpenSegment, TaskTimelineState


def close_open_segment(
    state: TaskTimelineState,
    *,
    sequence_end: int | None,
    monotonic_end_ns: int,
    wall_end: float,
) -> bool:
    """Finalize and append the current open segment, if any.

    Returns ``True`` when a segment was closed, ``False`` when there was
    nothing open. Pure with respect to ``state`` — caller's metrics update
    happens outside.
    """
    if state.open_segment is None:
        return False
    segment = finalize_segment(
        state.open_segment,
        sequence_end=sequence_end,
        monotonic_end_ns=monotonic_end_ns,
        wall_end=wall_end,
    )
    state.segments.append(segment)
    if segment.segment_type == "run":
        state.run_duration_ns += segment.duration_ns
    elif segment.segment_type == "wait":
        state.wait_duration_ns += segment.duration_ns
    state.open_segment = None
    return True


def open_new_segment(
    state: TaskTimelineState,
    *,
    segment_type: str,
    sequence_start: int | None,
    monotonic_start_ns: int,
    wall_start: float,
    target_state: TaskState,
) -> OpenSegment:
    """Open a fresh segment on ``state``. Caller MUST have closed any prior one."""
    segment = OpenSegment(
        task_id=state.task_id,
        segment_id=state.next_segment_id(),
        segment_type=segment_type,
        sequence_start=sequence_start,
        monotonic_start_ns=monotonic_start_ns,
        wall_start=wall_start,
        state=target_state.value,
        parent_task_id=state.parent_task_id,
        coroutine_name=state.coroutine_name,
        task_name=state.task_name,
    )
    state.open_segment = segment
    return segment


def finalize_task(
    state: TaskTimelineState,
    *,
    terminal_state: TaskState,
    monotonic_end_ns: int,
    wall_end: float,
) -> None:
    """Mark ``state`` terminal and record its end timestamps."""
    state.terminal_state = terminal_state.value
    state.terminated_at_monotonic_ns = monotonic_end_ns
    state.terminated_at_wall = wall_end


def total_duration_ns(state: TaskTimelineState, *, fallback_now_ns: int) -> int:
    """Total wall-vs-monotonic duration. Uses ``fallback_now_ns`` for active tasks."""
    if state.terminated_at_monotonic_ns is not None:
        return max(0, state.terminated_at_monotonic_ns - state.created_at_monotonic_ns)
    return max(0, fallback_now_ns - state.created_at_monotonic_ns)
