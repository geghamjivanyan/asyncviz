"""Compose the timeline snapshot from engine working state."""

from __future__ import annotations

from collections.abc import Iterable

from asyncviz.runtime.clock import RuntimeClock
from asyncviz.runtime.timeline.lifecycle import total_duration_ns
from asyncviz.runtime.timeline.models import (
    ActiveTimelineSegment,
    LifecycleSpan,
    TimelineSnapshot,
)
from asyncviz.runtime.timeline.projections import (
    project_coroutine_tracks,
    project_per_task_tracks,
    project_root_tracks,
)
from asyncviz.runtime.timeline.segments import view_active
from asyncviz.runtime.timeline.spans import TaskTimelineState


def build_lifecycle_span(
    state: TaskTimelineState,
    *,
    now_monotonic_ns: int,
) -> LifecycleSpan:
    """Materialize one task's :class:`LifecycleSpan` from its working state."""
    active = view_active(state.open_segment) if state.open_segment is not None else None
    return LifecycleSpan(
        task_id=state.task_id,
        parent_task_id=state.parent_task_id,
        coroutine_name=state.coroutine_name,
        task_name=state.task_name,
        created_at_monotonic_ns=state.created_at_monotonic_ns,
        created_at_wall=state.created_at_wall,
        terminated_at_monotonic_ns=state.terminated_at_monotonic_ns,
        terminated_at_wall=state.terminated_at_wall,
        terminal_state=state.terminal_state,
        total_duration_ns=total_duration_ns(state, fallback_now_ns=now_monotonic_ns),
        run_duration_ns=state.run_duration_ns,
        wait_duration_ns=state.wait_duration_ns,
        segment_count=len(state.segments),
        segments=list(state.segments),
        active_segment=active,
        depth=state.depth,
        root_task_id=state.root_task_id,
    )


def build_timeline_snapshot(
    states: Iterable[TaskTimelineState],
    clock: RuntimeClock,
    *,
    last_sequence: int,
    metrics_payload: dict[str, object] | None = None,
    track_kind: str = "task",
) -> TimelineSnapshot:
    """Compose the full :class:`TimelineSnapshot`.

    ``track_kind`` selects the grouping strategy. ``"task"`` is the default
    and matches the lowest-level rendering surface; ``"root"`` and
    ``"coroutine"`` collapse the same data along different axes.
    """
    now_ns = clock.monotonic_ns()
    spans: list[LifecycleSpan] = [
        build_lifecycle_span(state, now_monotonic_ns=now_ns) for state in states
    ]
    spans.sort(key=lambda s: (s.created_at_monotonic_ns, s.task_id))

    if track_kind == "root":
        tracks = project_root_tracks(spans)
    elif track_kind == "coroutine":
        tracks = project_coroutine_tracks(spans)
    else:
        tracks = project_per_task_tracks(spans)

    active_segments: list[ActiveTimelineSegment] = [
        span.active_segment for span in spans if span.active_segment is not None
    ]

    spans_by_task = {span.task_id: span for span in spans}

    return TimelineSnapshot(
        generated_at=clock.now(),
        generated_at_monotonic_ns=now_ns,
        runtime_id=str(clock.runtime_id),
        last_sequence=last_sequence,
        tracks=tracks,
        spans_by_task=spans_by_task,
        active_segments=active_segments,
        metrics=dict(metrics_payload or {}),
    )
