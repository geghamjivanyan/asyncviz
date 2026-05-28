from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TimelineSegment(BaseModel):
    """One contiguous execution interval on a task's timeline.

    Immutable. The engine produces a fresh :class:`TimelineSegment` value
    when an active span closes (e.g. ``RUNNING → WAITING`` closes a
    ``"run"`` segment).

    Field names are part of the public protocol — coordinate with the
    TypeScript ``TimelineSegment`` definition.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    segment_id: str
    segment_type: str  # "run" | "wait"
    sequence_start: int | None
    sequence_end: int | None
    monotonic_start_ns: int
    monotonic_end_ns: int
    duration_ns: int
    wall_start: float
    wall_end: float
    state: str
    parent_task_id: str | None = None
    coroutine_name: str | None = None
    task_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActiveTimelineSegment(BaseModel):
    """JSON-safe view of an open (not-yet-closed) segment.

    Distinct from :class:`TimelineSegment` because ``monotonic_end_ns``,
    ``wall_end``, ``duration_ns``, and ``sequence_end`` are necessarily
    undefined until the span closes. Snapshots embed this so the frontend
    can paint the still-running portion of a task without inventing fake
    end timestamps.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    segment_id: str
    segment_type: str
    sequence_start: int | None
    monotonic_start_ns: int
    wall_start: float
    state: str
    parent_task_id: str | None = None
    coroutine_name: str | None = None
    task_name: str | None = None


class LifecycleSpan(BaseModel):
    """Aggregate view of a task's whole lifetime on the timeline.

    Wraps the ordered list of :class:`TimelineSegment` plus rolled-up
    totals. Useful as a single-line summary in track displays.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    parent_task_id: str | None = None
    coroutine_name: str | None = None
    task_name: str | None = None
    created_at_monotonic_ns: int
    created_at_wall: float
    terminated_at_monotonic_ns: int | None = None
    terminated_at_wall: float | None = None
    terminal_state: str | None = None
    total_duration_ns: int
    run_duration_ns: int
    wait_duration_ns: int
    segment_count: int
    segments: list[TimelineSegment] = Field(default_factory=list)
    active_segment: ActiveTimelineSegment | None = None
    depth: int = 0
    root_task_id: str | None = None


class TimelineTrack(BaseModel):
    """A collection of :class:`LifecycleSpan`\\ s sharing a vertical lane.

    Track types:

      * ``"task"``      — exactly one span; one lane per task.
      * ``"root"``      — every span in the subtree of one root task.
      * ``"coroutine"`` — every span sharing a ``coroutine_name``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    track_id: str
    track_type: str
    label: str
    spans: list[LifecycleSpan] = Field(default_factory=list)
    earliest_monotonic_ns: int
    latest_monotonic_ns: int


class TimelineSnapshot(BaseModel):
    """Canonical timeline view emitted by :meth:`TimelineSegmentEngine.snapshot`.

    JSON-safe, deterministic, and replay-stable. Mirror this exactly in the
    TypeScript ``TimelineSnapshot`` interface.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    generated_at: float
    generated_at_monotonic_ns: int
    runtime_id: str
    last_sequence: int
    tracks: list[TimelineTrack] = Field(default_factory=list)
    spans_by_task: dict[str, LifecycleSpan] = Field(default_factory=dict)
    active_segments: list[ActiveTimelineSegment] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
