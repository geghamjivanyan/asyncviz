from __future__ import annotations

import threading
from collections.abc import Iterable
from typing import TYPE_CHECKING

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.timeline.buffering import DEFAULT_SEGMENT_LIMIT
from asyncviz.runtime.timeline.metrics import TimelineMetrics, TimelineMetricsSnapshot
from asyncviz.runtime.timeline.models import TimelineSegment, TimelineSnapshot
from asyncviz.runtime.timeline.normalization import (
    SegmentIntent,
    intent_for,
)
from asyncviz.runtime.timeline.queries import TimelineQueryService
from asyncviz.runtime.timeline.reducers import (
    TimelineReducerResult,
    reduce_close_and_finalize,
    reduce_create,
    reduce_open_run,
    reduce_open_wait,
)
from asyncviz.runtime.timeline.segments import view_active
from asyncviz.runtime.timeline.snapshots import build_timeline_snapshot
from asyncviz.runtime.timeline.spans import TaskTimelineState
from asyncviz.runtime.timeline.streaming import (
    TimelineDelta,
    TimelineDeltaKind,
    TimelineListener,
    TimelineSubscription,
    TimelineSubscriptionRegistry,
)
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.runtime.state import RuntimeStateStore, StateChange

logger = get_logger("runtime.timeline.engine")


class TimelineSegmentEngine:
    """Canonical timeline-segment generator for an AsyncViz runtime.

    Subscribes to :class:`RuntimeStateStore` notifications and incrementally
    turns lifecycle transitions into run / wait segments. Holds the only
    authoritative working set for active spans; finalized segments live in
    a bounded :class:`SegmentBuffer`.

    Lifecycle::

        engine = TimelineSegmentEngine()
        subscription = engine.bind(state_store)
        ...
        state_store.unsubscribe(subscription)
        engine.clear()
    """

    def __init__(
        self,
        *,
        clock: RuntimeClock | None = None,
        per_task_segment_limit: int = DEFAULT_SEGMENT_LIMIT,
    ) -> None:
        self._clock = clock or get_runtime_clock()
        self._lock = threading.RLock()
        self._states: dict[str, TaskTimelineState] = {}
        # ``SegmentBuffer`` is reserved for a future cap on long-running task
        # segment growth. Today we just bound the per-task list manually if
        # needed; for the common case (workflows < few thousand segments per
        # task) the working set fits in RAM easily.
        self._per_task_limit = per_task_segment_limit
        self._metrics = TimelineMetrics()
        self._queries = TimelineQueryService(self)
        self._last_sequence: int = 0
        self._subscriptions = TimelineSubscriptionRegistry()

    # ── identity ─────────────────────────────────────────────────────────
    @property
    def clock(self) -> RuntimeClock:
        return self._clock

    @property
    def queries(self) -> TimelineQueryService:
        return self._queries

    @property
    def last_sequence(self) -> int:
        with self._lock:
            return self._last_sequence

    # ── core apply ───────────────────────────────────────────────────────
    def apply_transition(
        self,
        *,
        task_id: str,
        target: TaskState,
        sequence: int | None,
        monotonic_ns: int,
        wall_seconds: float,
        parent_task_id: str | None = None,
        coroutine_name: str | None = None,
        task_name: str | None = None,
        depth: int = 0,
        root_task_id: str | None = None,
    ) -> TimelineReducerResult:
        """Process one lifecycle transition.

        Idempotent in the same direction the state store's reducers are:
        replays and duplicates are rejected, but in a way that doesn't
        corrupt finalized segments.
        """
        with self._lock:
            intent = intent_for(target)
            if intent is SegmentIntent.IGNORE:
                self._metrics.record_rejected()
                return TimelineReducerResult.rejected(
                    f"no segmentation intent for target {target.value!r}"
                )

            state = self._states.get(task_id)
            if state is None:
                state = TaskTimelineState(task_id=task_id)
                self._states[task_id] = state

            if intent is SegmentIntent.CREATE:
                result = reduce_create(
                    state,
                    sequence=sequence,
                    monotonic_ns=monotonic_ns,
                    wall_seconds=wall_seconds,
                    parent_task_id=parent_task_id,
                    coroutine_name=coroutine_name,
                    task_name=task_name,
                    depth=depth,
                    root_task_id=root_task_id,
                )
            elif intent is SegmentIntent.OPEN_RUN:
                result = reduce_open_run(
                    state,
                    sequence=sequence,
                    monotonic_ns=monotonic_ns,
                    wall_seconds=wall_seconds,
                )
            elif intent is SegmentIntent.OPEN_WAIT:
                result = reduce_open_wait(
                    state,
                    sequence=sequence,
                    monotonic_ns=monotonic_ns,
                    wall_seconds=wall_seconds,
                )
            else:  # CLOSE_AND_FINALIZE
                result = reduce_close_and_finalize(
                    state,
                    target_state=target,
                    sequence=sequence,
                    monotonic_ns=monotonic_ns,
                    wall_seconds=wall_seconds,
                )

            if not result.applied:
                self._metrics.record_rejected(invalid=result.invalid)
                return result

            self._metrics.record_applied()
            if result.closed_a_segment:
                self._metrics.record_segment_closed()
            if result.opened_segment_type is not None:
                self._metrics.record_segment_opened(result.opened_segment_type)
            if result.finalized_task:
                self._metrics.record_finalized_span()
            if sequence is not None and sequence > self._last_sequence:
                self._last_sequence = sequence

            # Capture snapshot data while still holding the lock so deltas
            # carry consistent values even if a concurrent apply races us.
            last_closed_segment = (
                state.segments[-1] if result.closed_a_segment and state.segments else None
            )
            opened_view = (
                view_active(state.open_segment)
                if result.opened_segment_type is not None and state.open_segment is not None
                else None
            )
            terminal_state = state.terminal_state if result.finalized_task else None

        # Notify outside the lock so subscribers don't serialize the apply path.
        self._emit_deltas_for(
            task_id=task_id,
            result=result,
            sequence=sequence,
            monotonic_ns=monotonic_ns,
            wall_seconds=wall_seconds,
            closed_segment=last_closed_segment,
            opened_segment=opened_view,
            terminal_state=terminal_state,
        )
        return result

    # ── subscription ─────────────────────────────────────────────────────
    def bind(self, store: RuntimeStateStore):
        """Subscribe to the state store's :class:`StateChange` stream.

        Returns the subscription handle; the lifespan tears it down on
        shutdown so the engine doesn't keep firing during teardown.
        """
        return store.subscribe(self._on_state_change_factory(store))

    def _on_state_change_factory(self, store: RuntimeStateStore):
        # Capture the store so the listener can look up per-task metadata
        # (parent / coroutine / depth / root) without re-walking the event.
        def listener(change: StateChange) -> None:
            event = change.event
            # Only :class:`Task*Event` carry a state-transition target. We
            # determine the target by event_type; non-task events are
            # ignored here.
            target = _event_to_state(event.event_type)
            if target is None:
                return
            task_id = getattr(event, "task_id", None)
            if not isinstance(task_id, str):
                return
            registry_task = store.registry.get(task_id)
            metadata = {
                "parent_task_id": registry_task.parent_task_id if registry_task else None,
                "coroutine_name": registry_task.coroutine_name if registry_task else None,
                "task_name": registry_task.task_name if registry_task else None,
                "depth": registry_task.depth if registry_task else 0,
                "root_task_id": registry_task.root_task_id if registry_task else None,
            }
            self.apply_transition(
                task_id=task_id,
                target=target,
                sequence=change.sequence,
                monotonic_ns=event.monotonic_ns,
                wall_seconds=event.timestamp,
                **metadata,  # type: ignore[arg-type]
            )

        return listener

    # ── subscriptions ────────────────────────────────────────────────────
    def subscribe(self, listener: TimelineListener) -> TimelineSubscription:
        """Subscribe to :class:`TimelineDelta` notifications.

        The streaming engine uses this to forward deltas onto the
        websocket. Test code subscribes here to assert on the delta
        sequence without parsing wire envelopes.
        """
        return self._subscriptions.add(listener)

    def unsubscribe(self, subscription: TimelineSubscription | int) -> bool:
        return self._subscriptions.remove(subscription)

    def _emit_deltas_for(
        self,
        *,
        task_id: str,
        result: TimelineReducerResult,
        sequence: int | None,
        monotonic_ns: int,
        wall_seconds: float,
        closed_segment: TimelineSegment | None,
        opened_segment: object | None,
        terminal_state: str | None,
    ) -> None:
        if self._subscriptions.count() == 0:
            return
        # Order: closed before opened so a (close → open) flip arrives as
        # the visible pair on the wire.
        if result.closed_a_segment and closed_segment is not None:
            self._notify(
                TimelineDelta(
                    kind=TimelineDeltaKind.SEGMENT_CLOSED,
                    task_id=task_id,
                    sequence=sequence,
                    monotonic_ns=monotonic_ns,
                    wall_seconds=wall_seconds,
                    segment=closed_segment,
                    closed_a_segment=True,
                )
            )
        if result.opened_segment_type is not None and opened_segment is not None:
            self._notify(
                TimelineDelta(
                    kind=TimelineDeltaKind.SEGMENT_OPENED,
                    task_id=task_id,
                    sequence=sequence,
                    monotonic_ns=monotonic_ns,
                    wall_seconds=wall_seconds,
                    open_segment=opened_segment,  # type: ignore[arg-type]
                )
            )
        if result.finalized_task:
            self._notify(
                TimelineDelta(
                    kind=TimelineDeltaKind.SPAN_FINALIZED,
                    task_id=task_id,
                    sequence=sequence,
                    monotonic_ns=monotonic_ns,
                    wall_seconds=wall_seconds,
                    terminal_state=terminal_state,
                )
            )

    def _notify(self, delta: TimelineDelta) -> None:
        for sub in self._subscriptions.listeners():
            try:
                sub.listener(delta)
            except Exception as exc:
                logger.warning(
                    "timeline subscriber %d failed for %s/%s: %s",
                    sub.id,
                    delta.task_id,
                    delta.kind.value,
                    exc,
                )

    # ── reads ────────────────────────────────────────────────────────────
    def state_of(self, task_id: str) -> TaskTimelineState | None:
        with self._lock:
            return self._states.get(task_id)

    def states_view(self) -> tuple[TaskTimelineState, ...]:
        with self._lock:
            return tuple(self._states.values())

    def segments_for(self, task_id: str) -> tuple[TimelineSegment, ...]:
        with self._lock:
            state = self._states.get(task_id)
            return tuple(state.segments) if state is not None else ()

    # ── lifecycle ────────────────────────────────────────────────────────
    def clear(self) -> None:
        with self._lock:
            self._states.clear()
            self._metrics.reset()
            self._last_sequence = 0

    def rebuild(
        self,
        records_by_task: dict[str, Iterable[object]] | None = None,
    ) -> int:
        """Reset and replay from the supplied per-task transition records.

        Mostly a thin wrapper around
        :func:`asyncviz.runtime.timeline.reconstruction.replay_history` —
        kept here so callers have a single ``engine.rebuild(...)`` entry.
        """
        from asyncviz.runtime.timeline.reconstruction import replay_history

        with self._lock:
            self.clear()
            count = replay_history(self, records_by_task or {}, metadata_by_task=None)
            self._metrics.record_rebuild()
            return count

    # ── snapshots / metrics ──────────────────────────────────────────────
    def snapshot(self, *, track_kind: str = "task") -> TimelineSnapshot:
        with self._lock:
            metrics = self._metrics.snapshot()
            return build_timeline_snapshot(
                tuple(self._states.values()),
                self._clock,
                last_sequence=self._last_sequence,
                metrics_payload=_metrics_to_payload(metrics),
                track_kind=track_kind,
            )

    def metrics_snapshot(self) -> TimelineMetricsSnapshot:
        return self._metrics.snapshot()


def _event_to_state(event_type: str) -> TaskState | None:
    return _EVENT_STATE_MAP.get(event_type)


_EVENT_STATE_MAP: dict[str, TaskState] = {
    "asyncio.task.created": TaskState.CREATED,
    "asyncio.task.started": TaskState.RUNNING,
    "asyncio.task.waiting": TaskState.WAITING,
    "asyncio.task.resumed": TaskState.RUNNING,
    "asyncio.task.completed": TaskState.COMPLETED,
    "asyncio.task.cancelled": TaskState.CANCELLED,
    "asyncio.task.failed": TaskState.FAILED,
}


def _metrics_to_payload(metrics: TimelineMetricsSnapshot) -> dict[str, object]:
    return {
        "transitions_applied": metrics.transitions_applied,
        "transitions_rejected": metrics.transitions_rejected,
        "segments_opened": metrics.segments_opened,
        "segments_closed": metrics.segments_closed,
        "segments_by_type": dict(metrics.segments_by_type),
        "invalid_transitions": metrics.invalid_transitions,
        "active_segments": metrics.active_segments,
        "finalized_spans": metrics.finalized_spans,
        "rebuilds_completed": metrics.rebuilds_completed,
    }
