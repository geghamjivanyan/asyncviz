"""Read-only query API over the engine's working state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from asyncviz.runtime.timeline.models import (
    ActiveTimelineSegment,
    LifecycleSpan,
    TimelineSegment,
    TimelineTrack,
)
from asyncviz.runtime.timeline.projections import (
    project_coroutine_tracks,
    project_per_task_tracks,
    project_root_tracks,
)
from asyncviz.runtime.timeline.segments import view_active
from asyncviz.runtime.timeline.snapshots import build_lifecycle_span

if TYPE_CHECKING:
    from asyncviz.runtime.timeline.engine import TimelineSegmentEngine


class TimelineQueryService:
    """Convenience wrapper around :class:`TimelineSegmentEngine` reads."""

    __slots__ = ("_engine",)

    def __init__(self, engine: TimelineSegmentEngine) -> None:
        self._engine = engine

    # ── segment-level queries ────────────────────────────────────────────
    def get_segments(self, task_id: str) -> tuple[TimelineSegment, ...]:
        return self._engine.segments_for(task_id)

    def get_active_segment(self, task_id: str) -> ActiveTimelineSegment | None:
        state = self._engine.state_of(task_id)
        if state is None or state.open_segment is None:
            return None
        return view_active(state.open_segment)

    def get_active_segments(self) -> list[ActiveTimelineSegment]:
        out: list[ActiveTimelineSegment] = []
        for state in self._engine.states_view():
            if state.open_segment is not None:
                out.append(view_active(state.open_segment))
        return out

    # ── span-level queries ───────────────────────────────────────────────
    def get_span(self, task_id: str) -> LifecycleSpan | None:
        state = self._engine.state_of(task_id)
        if state is None or not state.created:
            return None
        return build_lifecycle_span(
            state,
            now_monotonic_ns=self._engine.clock.monotonic_ns(),
        )

    def get_all_spans(self) -> list[LifecycleSpan]:
        now_ns = self._engine.clock.monotonic_ns()
        return [
            build_lifecycle_span(state, now_monotonic_ns=now_ns)
            for state in self._engine.states_view()
            if state.created
        ]

    # ── track-level queries ──────────────────────────────────────────────
    def get_per_task_tracks(self) -> list[TimelineTrack]:
        return project_per_task_tracks(self.get_all_spans())

    def get_root_tracks(self) -> list[TimelineTrack]:
        return project_root_tracks(self.get_all_spans())

    def get_coroutine_tracks(self) -> list[TimelineTrack]:
        return project_coroutine_tracks(self.get_all_spans())
