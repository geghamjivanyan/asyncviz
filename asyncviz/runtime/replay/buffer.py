from __future__ import annotations

import threading
import uuid
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.replay.checkpoints import CheckpointStore, ReplayCheckpoint
from asyncviz.runtime.replay.frames import ReplayFrame, frame_from_event
from asyncviz.runtime.replay.indexing import (
    build_batch,
    build_window,
    checkpoint_to_model,
)
from asyncviz.runtime.replay.models import (
    ReplayBatchModel,
    ReplayCheckpointModel,
    ReplaySelfMetricsModel,
    ReplaySnapshot,
)
from asyncviz.runtime.replay.retention import DEFAULT_FRAME_LIMIT, FrameRetention
from asyncviz.runtime.replay.streaming import (
    ReplayListener,
    ReplaySubscription,
    ReplaySubscriptionRegistry,
)
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.runtime.metrics import RuntimeMetricsAggregator
    from asyncviz.runtime.state import RuntimeStateStore, StateChange
    from asyncviz.runtime.timeline import TimelineSegmentEngine
    from asyncviz.runtime.warnings import RuntimeWarningManager

logger = get_logger("runtime.replay.buffer")


class EventReplayBuffer:
    """Canonical replay log for an AsyncViz runtime.

    Append-only frame ring + sequence index + checkpoint store. The bridge
    consults this for reconnect replays; future replay tools (scrubber,
    debugger) read directly through ``replay_since`` / ``replay_range``.

    Subscribes to :class:`RuntimeStateStore` state-change notifications and
    materializes one :class:`ReplayFrame` per applied event. Sequence
    ordering matches the queue's wire-order, so retained frames are a
    superset of what the websocket bridge broadcast.

    The buffer doesn't mutate state — it observes. Reconstruction helpers
    in :mod:`asyncviz.runtime.replay.reconstruction` use buffered frames to
    rebuild downstream subsystems on demand.
    """

    def __init__(
        self,
        *,
        clock: RuntimeClock | None = None,
        capacity: int = DEFAULT_FRAME_LIMIT,
        checkpoint_capacity: int = 16,
    ) -> None:
        self._clock = clock or get_runtime_clock()
        self._lock = threading.RLock()
        self._retention = FrameRetention(capacity=capacity)
        self._checkpoints = CheckpointStore(capacity=checkpoint_capacity)
        self._subscriptions = ReplaySubscriptionRegistry()
        self._last_sequence = 0
        self._frames_appended = 0
        self._replay_requests = 0
        self._replay_hits = 0
        self._replay_misses = 0
        self._checkpoints_created = 0
        self._reconstructions_completed = 0
        self._dispatch_count = 0
        self._dispatch_failures = 0

    # ── identity ─────────────────────────────────────────────────────────
    @property
    def clock(self) -> RuntimeClock:
        return self._clock

    @property
    def capacity(self) -> int:
        return self._retention.capacity

    @property
    def last_sequence(self) -> int:
        with self._lock:
            return self._last_sequence

    def __len__(self) -> int:
        return len(self._retention)

    # ── append path ──────────────────────────────────────────────────────
    def append_event(self, event: RuntimeEvent, *, sequence: int) -> ReplayFrame:
        """Record one event under ``sequence``. Returns the new frame."""
        frame = frame_from_event(event, sequence=sequence)
        with self._lock:
            self._retention.append(frame)
            if sequence > self._last_sequence:
                self._last_sequence = sequence
            self._frames_appended += 1
        self._notify(frame)
        return frame

    # ── state-store binding ──────────────────────────────────────────────
    def bind(self, store: RuntimeStateStore):
        """Subscribe to ``store``'s state-change stream."""

        def listener(change: StateChange) -> None:
            if change.sequence is None:
                return  # un-sequenced events don't belong in the replay log
            self.append_event(change.event, sequence=change.sequence)

        return store.subscribe(listener)

    # ── reads ────────────────────────────────────────────────────────────
    def get_frame(self, sequence: int) -> ReplayFrame | None:
        return self._retention.get(sequence)

    def latest_sequence(self) -> int:
        with self._lock:
            return self._last_sequence

    def oldest_retained_sequence(self) -> int | None:
        return self._retention.oldest_sequence()

    def newest_retained_sequence(self) -> int | None:
        return self._retention.newest_sequence()

    def covers(self, sequence: int) -> bool:
        return self._retention.covers(sequence)

    # ── replay batch construction ────────────────────────────────────────
    def replay_since(
        self,
        since_sequence: int,
        *,
        with_checkpoint: bool = False,
    ) -> ReplayBatchModel:
        """Return frames with ``sequence > since_sequence`` plus optional checkpoint.

        Checkpoint selection (when ``with_checkpoint=True``):

        * On a hit, return the freshest checkpoint with
          ``checkpoint.sequence <= since_sequence`` — the client applies it
          first, then streams the gap on top.
        * On a miss, return the *latest* checkpoint regardless of sequence
          — the client fast-forwards to that point and gives up on the
          older history no longer retained.
        """
        with self._lock:
            self._replay_requests += 1
            oldest = self._retention.oldest_sequence()
            newest = self._retention.newest_sequence()
            if not self._retention.covers(since_sequence):
                self._replay_misses += 1
                window = build_window(
                    requested_since=since_sequence,
                    requested_end=None,
                    frames=(),
                    hit=False,
                    oldest_available=oldest,
                    newest_available=newest,
                )
                checkpoint = self._checkpoints.latest() if with_checkpoint else None
                return build_batch(window=window, checkpoint=checkpoint)

            frames = self._retention.since(since_sequence)
            self._replay_hits += 1
            window = build_window(
                requested_since=since_sequence,
                requested_end=None,
                frames=frames,
                hit=True,
                oldest_available=oldest,
                newest_available=newest,
            )
            checkpoint = (
                self._checkpoints.find_for_replay(since_sequence=since_sequence)
                if with_checkpoint
                else None
            )
            return build_batch(window=window, checkpoint=checkpoint)

    def replay_range(self, start: int, end: int) -> ReplayBatchModel:
        """Return frames with ``start <= sequence <= end`` (inclusive)."""
        with self._lock:
            self._replay_requests += 1
            oldest = self._retention.oldest_sequence()
            newest = self._retention.newest_sequence()
            if oldest is None or end < oldest or start > (newest or 0):
                self._replay_misses += 1
                window = build_window(
                    requested_since=start,
                    requested_end=end,
                    frames=(),
                    hit=False,
                    oldest_available=oldest,
                    newest_available=newest,
                )
                return build_batch(window=window, checkpoint=None)
            frames = self._retention.range(start, end)
            self._replay_hits += 1
            window = build_window(
                requested_since=start,
                requested_end=end,
                frames=frames,
                hit=True,
                oldest_available=oldest,
                newest_available=newest,
            )
            return build_batch(window=window, checkpoint=None)

    # ── checkpoints ──────────────────────────────────────────────────────
    def create_checkpoint(
        self,
        *,
        label: str | None = None,
        state_store: RuntimeStateStore | None = None,
        timeline_engine: TimelineSegmentEngine | None = None,
        metrics_aggregator: RuntimeMetricsAggregator | None = None,
        warning_manager: RuntimeWarningManager | None = None,
    ) -> ReplayCheckpoint:
        """Capture a checkpoint pinned to the buffer's current sequence.

        Each subsystem reference is optional — pass only what you have
        wired up. Snapshots are serialized to JSON dicts so the
        checkpoint is self-contained.
        """
        with self._lock:
            now_ns = self._clock.monotonic_ns()
            wall = self._clock.now()
            sequence = self._last_sequence

        state_payload = (
            state_store.snapshot().model_dump(mode="json") if state_store is not None else None
        )
        timeline_payload = (
            timeline_engine.snapshot().model_dump(mode="json")
            if timeline_engine is not None
            else None
        )
        metrics_payload = (
            metrics_aggregator.snapshot().model_dump(mode="json")
            if metrics_aggregator is not None
            else None
        )
        warnings_payload = (
            warning_manager.snapshot().model_dump(mode="json")
            if warning_manager is not None
            else None
        )

        checkpoint = ReplayCheckpoint(
            checkpoint_id=uuid.uuid4().hex,
            sequence=sequence,
            monotonic_ns=now_ns,
            wall_seconds=wall,
            runtime_id=str(self._clock.runtime_id),
            state=state_payload,
            timeline=timeline_payload,
            metrics=metrics_payload,
            warnings=warnings_payload,
            label=label,
        )
        with self._lock:
            self._checkpoints.add(checkpoint)
            self._checkpoints_created += 1
        return checkpoint

    def latest_checkpoint(self) -> ReplayCheckpoint | None:
        return self._checkpoints.latest()

    def find_checkpoint_for_replay(
        self,
        *,
        since_sequence: int,
    ) -> ReplayCheckpoint | None:
        return self._checkpoints.find_for_replay(since_sequence=since_sequence)

    def checkpoints_view(self) -> tuple[ReplayCheckpoint, ...]:
        return self._checkpoints.snapshot()

    # ── reconstruction ──────────────────────────────────────────────────
    def replay_into_state(
        self,
        store: RuntimeStateStore,
        *,
        since_sequence: int = 0,
    ) -> int:
        """Replay every frame newer than ``since_sequence`` into ``store``."""
        from asyncviz.runtime.replay.reconstruction import replay_into_state_store

        frames = self._retention.since(since_sequence)
        count = replay_into_state_store(frames, store)
        with self._lock:
            self._reconstructions_completed += 1
        return count

    def replay_into_metrics(
        self,
        aggregator: RuntimeMetricsAggregator,
        *,
        since_sequence: int = 0,
    ) -> int:
        from asyncviz.runtime.replay.reconstruction import replay_into_metrics

        frames = self._retention.since(since_sequence)
        count = replay_into_metrics(frames, aggregator)
        with self._lock:
            self._reconstructions_completed += 1
        return count

    def replay_into_warnings(
        self,
        manager: RuntimeWarningManager,
        *,
        since_sequence: int = 0,
    ) -> int:
        from asyncviz.runtime.replay.reconstruction import replay_into_warning_manager

        frames = self._retention.since(since_sequence)
        count = replay_into_warning_manager(frames, manager)
        with self._lock:
            self._reconstructions_completed += 1
        return count

    # ── subscriptions ────────────────────────────────────────────────────
    def subscribe(self, listener: ReplayListener) -> ReplaySubscription:
        return self._subscriptions.add(listener)

    def unsubscribe(self, subscription: ReplaySubscription | int) -> bool:
        return self._subscriptions.remove(subscription)

    # ── snapshots / metrics ──────────────────────────────────────────────
    def snapshot(self) -> ReplaySnapshot:
        with self._lock:
            oldest = self._retention.oldest_sequence()
            newest = self._retention.newest_sequence()
            latest_checkpoint = self._checkpoints.latest()
            checkpoints_models = [checkpoint_to_model(cp) for cp in self._checkpoints.snapshot()]
            latest_model: ReplayCheckpointModel | None = (
                checkpoint_to_model(latest_checkpoint) if latest_checkpoint else None
            )
            self_metrics = ReplaySelfMetricsModel(
                frames_appended=self._frames_appended,
                frames_evicted=self._retention.evicted_count,
                replay_requests=self._replay_requests,
                replay_hits=self._replay_hits,
                replay_misses=self._replay_misses,
                checkpoints_created=self._checkpoints_created,
                reconstructions_completed=self._reconstructions_completed,
                subscription_dispatches=self._dispatch_count,
                subscription_failures=self._dispatch_failures,
            )
            return ReplaySnapshot(
                generated_at=self._clock.now(),
                generated_at_monotonic_ns=self._clock.monotonic_ns(),
                runtime_id=str(self._clock.runtime_id),
                capacity=self._retention.capacity,
                frame_count=len(self._retention),
                oldest_sequence=oldest,
                newest_sequence=newest,
                oldest_evicted_sequence=self._retention.oldest_evicted_sequence,
                checkpoints=checkpoints_models,
                latest_checkpoint=latest_model,
                self_metrics=self_metrics,
            )

    def self_metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "frames_appended": self._frames_appended,
                "frames_evicted": self._retention.evicted_count,
                "frames_retained": len(self._retention),
                "replay_requests": self._replay_requests,
                "replay_hits": self._replay_hits,
                "replay_misses": self._replay_misses,
                "checkpoints_created": self._checkpoints_created,
                "reconstructions_completed": self._reconstructions_completed,
            }

    # ── lifecycle ────────────────────────────────────────────────────────
    def clear(self) -> None:
        with self._lock:
            self._retention.clear()
            self._checkpoints.clear()
            self._last_sequence = 0
            self._frames_appended = 0
            self._replay_requests = 0
            self._replay_hits = 0
            self._replay_misses = 0
            self._checkpoints_created = 0
            self._reconstructions_completed = 0

    def rebuild(self, events_with_sequences: Iterable[tuple[RuntimeEvent, int]]) -> int:
        """Reset and re-append from ``events_with_sequences``. Returns count."""
        self.clear()
        count = 0
        for event, sequence in events_with_sequences:
            self.append_event(event, sequence=sequence)
            count += 1
        return count

    # ── internals ────────────────────────────────────────────────────────
    def _notify(self, frame: ReplayFrame) -> None:
        if not self._subscriptions.count():
            return
        failures = 0
        for sub in self._subscriptions.listeners():
            try:
                sub.listener(frame)
            except Exception as exc:
                failures += 1
                logger.warning(
                    "replay subscriber %d failed for seq=%d: %s",
                    sub.id,
                    frame.sequence,
                    exc,
                )
        with self._lock:
            self._dispatch_count += 1
            self._dispatch_failures += failures
