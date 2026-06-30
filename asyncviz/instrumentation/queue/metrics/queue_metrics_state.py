"""Per-queue aggregated state.

One :class:`QueueAggregateState` per tracked queue. Owns the occupancy
window, throughput counters, contention tracker, wait digests, and
pressure scorer. The engine routes raw queue events here based on
``queue_id`` and asks for a snapshot whenever it needs to emit.

``apply_event`` is intentionally side-effect-pure aside from updating
internal counters. The *decision* to emit an event lives on the engine;
this layer just maintains analytics state. That split lets us rebuild
state from a replay event stream without firing duplicate emissions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from asyncviz.instrumentation.queue.metrics.queue_metrics_configuration import (
    QueueMetricsConfig,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_contention import (
    ContentionTracker,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    QueueMetricsRecord,
    QueueOccupancySnapshot,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_pressure import (
    PressureScorer,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_statistics import (
    WaitDigest,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_throughput import (
    ThroughputCounters,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_windows import (
    OccupancyWindow,
)
from asyncviz.runtime.events.models.queue import (
    QueueCancelledEvent,
    QueueCreatedEvent,
    QueueEmptyWaitEvent,
    QueueFullWaitEvent,
    QueueGetEvent,
    QueuePutEvent,
    QueueTaskDoneEvent,
)


@dataclass(frozen=True, slots=True)
class ApplyOutcome:
    """What changed after :meth:`QueueAggregateState.apply_event`.

    The engine inspects these flags to decide which (if any) aggregated
    event to emit. Keeping the decision off the state class lets the
    state be replayed quietly (rebuild flow) or loudly (live flow) from
    the same code.
    """

    accepted: bool = False
    events_since_last_emission: int = 0
    occupancy_changed: bool = False
    blocked_transitioned: bool = False
    """``True`` when the blocked-producer or blocked-consumer count
    transitioned from 0 → ≥1 (or below → at-or-above the configured
    contention threshold)."""

    contention_kind: str = "producers"
    saturation_entered: bool = False
    saturation_exited: bool = False


@dataclass(slots=True)
class QueueAggregateState:
    queue_id: str
    queue_kind: str
    maxsize: int
    config: QueueMetricsConfig
    revision: int = 0
    """Monotonic per-queue counter — bumped on every event that touches
    this state, regardless of whether an emission fires."""

    last_emitted_revision: int = 0
    last_emit_monotonic: float = 0.0
    last_observed_size: int = 0

    occupancy: OccupancyWindow = field(init=False)
    throughput: ThroughputCounters = field(init=False)
    contention: ContentionTracker = field(init=False)
    pressure: PressureScorer = field(init=False)
    put_wait: WaitDigest = field(init=False)
    get_wait: WaitDigest = field(init=False)
    finalized: bool = False
    last_emitted_level: str = "calm"
    """Cached level we last published. Used by the engine to detect
    pressure-level transitions across emissions."""

    def __post_init__(self) -> None:
        self.occupancy = OccupancyWindow(capacity=self.config.occupancy_window_size)
        self.throughput = ThroughputCounters(window_seconds=self.config.throughput_window_seconds)
        self.contention = ContentionTracker()
        self.pressure = PressureScorer(config=self.config)
        self.put_wait = WaitDigest(capacity=self.config.wait_reservoir_size)
        self.get_wait = WaitDigest(capacity=self.config.wait_reservoir_size)

    # ── apply ─────────────────────────────────────────────────────────

    def apply_event(self, event: Any, *, monotonic_seconds: float) -> ApplyOutcome:
        if self.finalized:
            return ApplyOutcome(accepted=False)
        self.revision += 1
        snapshot = _read_snapshot(event)
        prev_blocked_producers = self.contention.blocked_producers
        prev_blocked_consumers = self.contention.blocked_consumers
        prev_saturated = self.pressure.saturated

        size_now = self._extract_size(snapshot)
        occupancy_changed = size_now != self.last_observed_size
        if occupancy_changed:
            self.occupancy.observe(size_now)
            self.last_observed_size = size_now

        # Maxsize can be late-bound (lazy registration sees maxsize=0 then
        # gets corrected on the first put). Always trust the freshest one.
        snapshot_max = snapshot.get("maxsize")
        if isinstance(snapshot_max, int) and snapshot_max > 0:
            self.maxsize = snapshot_max

        self.contention.update_blocked(
            producers=int(snapshot.get("blocked_putters", 0) or 0),
            consumers=int(snapshot.get("blocked_getters", 0) or 0),
        )

        if isinstance(event, QueueCreatedEvent):
            pass
        elif isinstance(event, QueuePutEvent):
            self.throughput.record_put(monotonic_seconds=monotonic_seconds, nowait=event.nowait)
            if event.blocked:
                self.contention.record_blocked_put()
                if event.wait_seconds is not None:
                    self.put_wait.observe(event.wait_seconds)
        elif isinstance(event, QueueGetEvent):
            self.throughput.record_get(monotonic_seconds=monotonic_seconds, nowait=event.nowait)
            if event.blocked:
                self.contention.record_blocked_get()
                if event.wait_seconds is not None:
                    self.get_wait.observe(event.wait_seconds)
        elif isinstance(event, QueueFullWaitEvent):
            self.contention.record_full_wait()
        elif isinstance(event, QueueEmptyWaitEvent):
            self.contention.record_empty_wait()
        elif isinstance(event, QueueTaskDoneEvent):
            self.throughput.record_task_done()
        elif isinstance(event, QueueCancelledEvent):
            self.throughput.record_cancelled()
            self.contention.record_cancelled()
            if event.wait_seconds is not None:
                # Attribute the wait to the operation that was cancelled.
                if event.operation == "put":
                    self.put_wait.observe(event.wait_seconds)
                else:
                    self.get_wait.observe(event.wait_seconds)
        else:
            # Unknown event subclass — accept but make no aggregate changes.
            return ApplyOutcome(
                accepted=True,
                events_since_last_emission=self.revision - self.last_emitted_revision,
                occupancy_changed=False,
            )

        contention_threshold = self.config.contention_blocked_threshold
        blocked_transitioned, contention_kind = _blocked_transition(
            prev_producers=prev_blocked_producers,
            prev_consumers=prev_blocked_consumers,
            now_producers=self.contention.blocked_producers,
            now_consumers=self.contention.blocked_consumers,
            threshold=contention_threshold,
        )

        occupancy_ratio = self._occupancy_ratio()
        saturated_now = occupancy_ratio >= self.config.saturation_threshold
        saturation_entered = saturated_now and not prev_saturated
        saturation_exited = (
            prev_saturated and occupancy_ratio < self.config.saturation_recovery_threshold
        )
        # Re-arm so the next saturation crossing fires again.
        if saturation_entered:
            self.pressure.mark_saturated(saturated=True)
        if saturation_exited:
            self.pressure.mark_saturated(saturated=False)

        return ApplyOutcome(
            accepted=True,
            events_since_last_emission=self.revision - self.last_emitted_revision,
            occupancy_changed=occupancy_changed,
            blocked_transitioned=blocked_transitioned,
            contention_kind=contention_kind,
            saturation_entered=saturation_entered,
            saturation_exited=saturation_exited,
        )

    # ── snapshot ──────────────────────────────────────────────────────

    def snapshot(self, *, monotonic_seconds: float | None = None) -> QueueMetricsRecord:
        occupancy_ratio = self._occupancy_ratio()
        throughput_snap = self.throughput.snapshot(monotonic_seconds=monotonic_seconds)
        pressure_snap = self.pressure.evaluate(
            occupancy_ratio=occupancy_ratio,
            blocked_producers=self.contention.blocked_producers,
            blocked_consumers=self.contention.blocked_consumers,
            put_rate=throughput_snap.put_rate,
            get_rate=throughput_snap.get_rate,
        )
        occupancy_snap = QueueOccupancySnapshot(
            current_size=self.last_observed_size,
            peak_size=self.occupancy.peak,
            occupancy_ratio=occupancy_ratio,
            mean_occupancy=self.occupancy.mean(),
            sample_count=len(self.occupancy.samples),
        )
        return QueueMetricsRecord(
            queue_id=self.queue_id,
            queue_kind=self.queue_kind,
            maxsize=self.maxsize,
            sequence=self.revision,
            occupancy=occupancy_snap,
            throughput=throughput_snap,
            contention=self.contention.snapshot(),
            pressure=pressure_snap,
            put_wait=self.put_wait.snapshot(),
            get_wait=self.get_wait.snapshot(),
        )

    def mark_emitted(self, *, monotonic_seconds: float) -> None:
        self.last_emitted_revision = self.revision
        self.last_emit_monotonic = monotonic_seconds

    def finalize(self) -> None:
        self.finalized = True

    # ── internals ─────────────────────────────────────────────────────

    def _extract_size(self, snapshot: dict[str, Any]) -> int:
        size = snapshot.get("size")
        return int(size) if isinstance(size, int) else self.last_observed_size

    def _occupancy_ratio(self) -> float:
        if self.maxsize <= 0:
            return 0.0
        ratio = self.last_observed_size / self.maxsize
        return max(0.0, min(1.0, ratio))


def _read_snapshot(event: Any) -> dict[str, Any]:
    snap = getattr(event, "snapshot", None)
    return snap if isinstance(snap, dict) else {}


def _blocked_transition(
    *,
    prev_producers: int,
    prev_consumers: int,
    now_producers: int,
    now_consumers: int,
    threshold: int,
) -> tuple[bool, str]:
    """Detect a was-below → now-at-or-above transition for either side.

    Returns ``(transitioned, kind)`` where ``kind`` is ``"producers"``,
    ``"consumers"``, or ``"both"`` when both sides crossed simultaneously.
    """
    producers_crossed = prev_producers < threshold <= now_producers
    consumers_crossed = prev_consumers < threshold <= now_consumers
    if producers_crossed and consumers_crossed:
        return True, "both"
    if producers_crossed:
        return True, "producers"
    if consumers_crossed:
        return True, "consumers"
    return False, "producers"
