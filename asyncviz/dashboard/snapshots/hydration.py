"""Canonical snapshot generation orchestrator.

The :class:`SnapshotService` is the single place that aggregates the
runtime's sub-snapshots into a :class:`RuntimeSnapshot`. It owns one
lock — held across the entire capture — so every sub-snapshot sees a
consistent ``last_sequence`` cursor.

The service does *not* re-serialize anything: each sub-snapshot is the
exact Pydantic model the source service emits. The composition is the
contract; the underlying schemas are reused verbatim.
"""

from __future__ import annotations

import threading
import uuid
from time import monotonic_ns
from typing import TYPE_CHECKING

from asyncviz.dashboard.snapshots.metrics import (
    SnapshotMetrics,
    SnapshotMetricsSnapshot,
)
from asyncviz.dashboard.snapshots.models import (
    SNAPSHOT_PROTOCOL_VERSION,
    HydrationOptions,
    RuntimeSnapshot,
    SnapshotConsistency,
    SnapshotMetadata,
)
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.runtime.clock import RuntimeClock
    from asyncviz.runtime.metrics import RuntimeMetricsAggregator
    from asyncviz.runtime.queue import InternalEventQueue
    from asyncviz.runtime.replay import EventReplayBuffer
    from asyncviz.runtime.state import RuntimeStateStore
    from asyncviz.runtime.timeline import TimelineSegmentEngine
    from asyncviz.runtime.warnings import RuntimeWarningManager

logger = get_logger("dashboard.snapshots.hydration")


class SnapshotService:
    """Compose a :class:`RuntimeSnapshot` from in-process runtime services.

    Single-lock generation. ``capture`` is safe to call from any thread,
    and from any number of concurrent callers — the lock serializes
    them. The lock is held for the whole capture so the resulting
    sub-snapshots all reflect the same view of the runtime.

    Identity of upstream services is captured at construction time; the
    services themselves are mutable, so the snapshot reflects the
    *current* state of each one at capture time.
    """

    def __init__(
        self,
        *,
        clock: RuntimeClock,
        state_store: RuntimeStateStore,
        timeline_engine: TimelineSegmentEngine,
        metrics_aggregator: RuntimeMetricsAggregator,
        warning_manager: RuntimeWarningManager,
        replay_buffer: EventReplayBuffer,
        event_queue: InternalEventQueue | None = None,
    ) -> None:
        self._clock = clock
        self._state_store = state_store
        self._timeline_engine = timeline_engine
        self._metrics_aggregator = metrics_aggregator
        self._warning_manager = warning_manager
        self._replay_buffer = replay_buffer
        self._event_queue = event_queue
        self._lock = threading.Lock()
        self._metrics = SnapshotMetrics()

    @property
    def metrics(self) -> SnapshotMetrics:
        return self._metrics

    def metrics_snapshot(self) -> SnapshotMetricsSnapshot:
        return self._metrics.snapshot()

    def capture(
        self,
        options: HydrationOptions | None = None,
    ) -> RuntimeSnapshot:
        """Capture the canonical runtime snapshot.

        The sequence-consistency boundary works like this:

        1. Acquire the snapshot lock — serializes concurrent captures.
        2. Read the clock to nail down ``last_sequence`` + timestamps.
        3. Call each sub-source's ``snapshot()`` once — each is itself
           internally locked so it returns a deterministic view.
        4. Release the lock and build the envelope.

        The lock is *not* held across event-bus or queue writes, so
        the runtime continues processing events around captures; what
        the lock prevents is two concurrent captures interleaving each
        other's views.
        """
        options = options or HydrationOptions()
        started_ns = monotonic_ns()

        with self._lock:
            clock_snapshot = self._clock.snapshot()
            last_sequence = clock_snapshot.current_sequence

            state_snapshot = (
                self._state_store.snapshot(
                    include_projections=options.include_projections,
                    include_transitions=options.include_transitions,
                )
                if options.include_state
                else None
            )
            timeline_snapshot = (
                self._timeline_engine.snapshot(track_kind=options.timeline_track_kind)
                if options.include_timeline
                else None
            )
            metrics_snapshot = (
                self._metrics_aggregator.snapshot() if options.include_metrics else None
            )
            if options.include_warnings:
                if options.evaluate_warnings:
                    # Refresh snapshot-driven detectors before the read so
                    # the embedded view matches the dashboard's ``/warnings``
                    # endpoint behavior (which evaluates by default).
                    self._warning_manager.evaluate()
                warning_snapshot = self._warning_manager.snapshot()
            else:
                warning_snapshot = None
            replay_snapshot = self._replay_buffer.snapshot() if options.include_replay else None
            queue_snapshot = (
                self._event_queue.snapshot()
                if options.include_queue and self._event_queue is not None
                else None
            )

        included, skipped = _classify_sources(
            options,
            state=state_snapshot is not None,
            timeline=timeline_snapshot is not None,
            metrics=metrics_snapshot is not None,
            warnings=warning_snapshot is not None,
            replay=replay_snapshot is not None,
            queue=queue_snapshot is not None,
        )

        last_event_id = state_snapshot.last_event_id if state_snapshot is not None else None
        # Use the buffer's canonical ``covers`` predicate so the semantic of
        # ``replay_window_hit`` matches what ``/api/runtime/replay/since`` will
        # actually return — no parallel rules.
        if options.since_sequence is None:
            window_hit = True
        else:
            window_hit = self._replay_buffer.covers(options.since_sequence)
        consistency = SnapshotConsistency(
            last_sequence=last_sequence,
            last_event_id=last_event_id,
            generated_at_monotonic_ns=clock_snapshot.monotonic_now_ns,
            generated_at=clock_snapshot.wall_now_seconds,
            oldest_retained_sequence=(
                replay_snapshot.oldest_sequence if replay_snapshot is not None else None
            ),
            newest_retained_sequence=(
                replay_snapshot.newest_sequence if replay_snapshot is not None else None
            ),
            replay_window_hit=window_hit,
        )

        snapshot_id = uuid.uuid4().hex
        # Bytes are stamped via ``model_dump_json`` once: see the size
        # measurement below. We need the metadata first because the
        # envelope embeds it; the size update happens post-build.
        metadata = SnapshotMetadata(
            snapshot_version=SNAPSHOT_PROTOCOL_VERSION,
            snapshot_id=snapshot_id,
            runtime_id=str(clock_snapshot.runtime_id),
            generated_at=clock_snapshot.wall_now_seconds,
            generated_at_monotonic_ns=clock_snapshot.monotonic_now_ns,
            generation_duration_ns=0,
            payload_bytes=0,
            is_full=options.is_full,
            included_sources=included,
            skipped_sources=skipped,
        )

        snapshot = RuntimeSnapshot(
            metadata=metadata,
            consistency=consistency,
            clock=clock_snapshot,
            state=state_snapshot,
            timeline=timeline_snapshot,
            metrics=metrics_snapshot,
            warnings=warning_snapshot,
            replay=replay_snapshot,
            queue=queue_snapshot,
        )

        # Now stamp size + duration. We rebuild the envelope rather than
        # mutating the frozen model — Pydantic v2 frozen models forbid
        # ``__setattr__``, so ``model_copy(update=...)`` is the path.
        payload_bytes = len(snapshot.model_dump_json())
        duration_ns = monotonic_ns() - started_ns
        snapshot = snapshot.model_copy(
            update={
                "metadata": metadata.model_copy(
                    update={
                        "generation_duration_ns": duration_ns,
                        "payload_bytes": payload_bytes,
                    }
                ),
            }
        )

        self._metrics.record_generation(
            duration_ns=duration_ns,
            payload_bytes=payload_bytes,
            filtered=not options.is_full,
            sources_skipped=len(skipped),
        )
        logger.debug(
            "snapshot %s generated in %d ns (%d bytes, filtered=%s, skipped=%s)",
            snapshot_id,
            duration_ns,
            payload_bytes,
            not options.is_full,
            skipped or "none",
        )
        return snapshot


def _classify_sources(
    options: HydrationOptions,
    *,
    state: bool,
    timeline: bool,
    metrics: bool,
    warnings: bool,
    replay: bool,
    queue: bool,
) -> tuple[list[str], list[str]]:
    """Categorize each source as included / skipped for the metadata envelope.

    A source is "skipped" when the caller's options turned it off OR the
    upstream service is missing (e.g. no event queue bound). Either way
    the consumer needs to know which sub-snapshots are present without
    poking at each ``None`` field; this is the canonical surface.
    """
    classification: dict[str, tuple[bool, bool]] = {
        "state": (options.include_state, state),
        "timeline": (options.include_timeline, timeline),
        "metrics": (options.include_metrics, metrics),
        "warnings": (options.include_warnings, warnings),
        "replay": (options.include_replay, replay),
        "queue": (options.include_queue, queue),
    }
    included = [name for name, (_requested, present) in classification.items() if present]
    skipped = [name for name, (_requested, present) in classification.items() if not present]
    # Stable order for protocol determinism.
    included.sort()
    skipped.sort()
    return included, skipped
