"""Canonical timeline segment engine.

Public surface:

* :class:`TimelineSegmentEngine` — the runtime's authoritative timeline
  generator. Subscribes to :class:`RuntimeStateStore` notifications and
  turns lifecycle transitions into :class:`TimelineSegment` values.
* :class:`TimelineSegment` / :class:`ActiveTimelineSegment` /
  :class:`LifecycleSpan` / :class:`TimelineTrack` / :class:`TimelineSnapshot`
  — Pydantic wire models. Coordinate with the TypeScript ``Timeline*``
  interfaces.
* :class:`TimelineMetrics` / :class:`TimelineMetricsSnapshot` —
  observability.
* :class:`TimelineQueryService` — read-only convenience over the engine.
* :func:`replay_history` / :func:`replay_state_store` — replay reconstruction
  entry points.
* :class:`SegmentIntent` / :func:`intent_for` — pure decision layer
  testable in isolation.
* exceptions — :class:`TimelineError`,
  :class:`InvalidSegmentTransitionError`, :class:`SegmentReconstructionError`.

Design rule: a runtime has exactly **one** :class:`TimelineSegmentEngine`.
It composes the :class:`RuntimeStateStore` rather than duplicating its
indexes. Mutations go through ``apply_transition``; reads through
:attr:`queries` or :meth:`snapshot`.
"""

from asyncviz.runtime.timeline.buffering import (
    DEFAULT_SEGMENT_LIMIT,
    SegmentBuffer,
)
from asyncviz.runtime.timeline.engine import TimelineSegmentEngine
from asyncviz.runtime.timeline.exceptions import (
    InvalidSegmentTransitionError,
    SegmentBufferOverflowError,
    SegmentReconstructionError,
    TimelineError,
)
from asyncviz.runtime.timeline.lifecycle import (
    close_open_segment,
    finalize_task,
    open_new_segment,
    total_duration_ns,
)
from asyncviz.runtime.timeline.metrics import (
    TimelineMetrics,
    TimelineMetricsSnapshot,
)
from asyncviz.runtime.timeline.models import (
    ActiveTimelineSegment,
    LifecycleSpan,
    TimelineSegment,
    TimelineSnapshot,
    TimelineTrack,
)
from asyncviz.runtime.timeline.normalization import (
    INTENT_BY_TARGET,
    SegmentIntent,
    TransitionIntent,
    intent_for,
    is_terminal_intent,
)
from asyncviz.runtime.timeline.projections import (
    project_coroutine_tracks,
    project_per_task_tracks,
    project_root_tracks,
)
from asyncviz.runtime.timeline.queries import TimelineQueryService
from asyncviz.runtime.timeline.reconstruction import (
    is_terminal_state,
    replay_history,
    replay_state_store,
)
from asyncviz.runtime.timeline.reducers import (
    TimelineReducerResult,
    reduce_close_and_finalize,
    reduce_create,
    reduce_open_run,
    reduce_open_wait,
)
from asyncviz.runtime.timeline.segments import finalize_segment, view_active
from asyncviz.runtime.timeline.snapshots import (
    build_lifecycle_span,
    build_timeline_snapshot,
)
from asyncviz.runtime.timeline.spans import OpenSegment, TaskTimelineState
from asyncviz.runtime.timeline.streaming import (
    TimelineDelta,
    TimelineDeltaKind,
    TimelineListener,
    TimelineSubscription,
    TimelineSubscriptionRegistry,
)

__all__ = [
    "DEFAULT_SEGMENT_LIMIT",
    "INTENT_BY_TARGET",
    "ActiveTimelineSegment",
    "InvalidSegmentTransitionError",
    "LifecycleSpan",
    "OpenSegment",
    "SegmentBuffer",
    "SegmentBufferOverflowError",
    "SegmentIntent",
    "SegmentReconstructionError",
    "TaskTimelineState",
    "TimelineDelta",
    "TimelineDeltaKind",
    "TimelineError",
    "TimelineListener",
    "TimelineMetrics",
    "TimelineMetricsSnapshot",
    "TimelineQueryService",
    "TimelineReducerResult",
    "TimelineSegment",
    "TimelineSegmentEngine",
    "TimelineSnapshot",
    "TimelineSubscription",
    "TimelineSubscriptionRegistry",
    "TimelineTrack",
    "TransitionIntent",
    "build_lifecycle_span",
    "build_timeline_snapshot",
    "close_open_segment",
    "finalize_segment",
    "finalize_task",
    "intent_for",
    "is_terminal_intent",
    "is_terminal_state",
    "open_new_segment",
    "project_coroutine_tracks",
    "project_per_task_tracks",
    "project_root_tracks",
    "reduce_close_and_finalize",
    "reduce_create",
    "reduce_open_run",
    "reduce_open_wait",
    "replay_history",
    "replay_state_store",
    "total_duration_ns",
    "view_active",
]
