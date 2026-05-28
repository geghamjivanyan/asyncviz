"""Pure constructors for :class:`TimelineSegment` / :class:`ActiveTimelineSegment`.

Kept apart from the mutable working set so the build steps stay easy to
unit-test against bare values.
"""

from __future__ import annotations

from asyncviz.runtime.timeline.models import ActiveTimelineSegment, TimelineSegment
from asyncviz.runtime.timeline.spans import OpenSegment


def finalize_segment(
    open_segment: OpenSegment,
    *,
    sequence_end: int | None,
    monotonic_end_ns: int,
    wall_end: float,
) -> TimelineSegment:
    """Convert an :class:`OpenSegment` into an immutable :class:`TimelineSegment`.

    ``duration_ns`` is clamped to non-negative — a monotonic anomaly would
    otherwise produce surprising negative durations on the wire.
    """
    duration = max(0, monotonic_end_ns - open_segment.monotonic_start_ns)
    return TimelineSegment(
        task_id=open_segment.task_id,
        segment_id=open_segment.segment_id,
        segment_type=open_segment.segment_type,
        sequence_start=open_segment.sequence_start,
        sequence_end=sequence_end,
        monotonic_start_ns=open_segment.monotonic_start_ns,
        monotonic_end_ns=monotonic_end_ns,
        duration_ns=duration,
        wall_start=open_segment.wall_start,
        wall_end=wall_end,
        state=open_segment.state,
        parent_task_id=open_segment.parent_task_id,
        coroutine_name=open_segment.coroutine_name,
        task_name=open_segment.task_name,
        metadata=dict(open_segment.metadata),
    )


def view_active(open_segment: OpenSegment) -> ActiveTimelineSegment:
    """JSON-safe view of an open segment for snapshot transport."""
    return ActiveTimelineSegment(
        task_id=open_segment.task_id,
        segment_id=open_segment.segment_id,
        segment_type=open_segment.segment_type,
        sequence_start=open_segment.sequence_start,
        monotonic_start_ns=open_segment.monotonic_start_ns,
        wall_start=open_segment.wall_start,
        state=open_segment.state,
        parent_task_id=open_segment.parent_task_id,
        coroutine_name=open_segment.coroutine_name,
        task_name=open_segment.task_name,
    )
