"""Canonical queue metrics engine.

Lifecycle::

    engine = QueueMetricsEngine(bus=bus)
    engine.start()              # subscribes to the bus
    ...                          # runtime emits queue events; engine aggregates
    engine.snapshot()           # build a diagnostics snapshot
    sub = engine.subscribe(cb)  # receive QueueMetricsDelta callbacks
    engine.stop()               # idempotent unsubscribe

The engine processes the seven raw asyncio.queue.* events into:

* per-queue aggregated state (occupancy, throughput, contention, pressure)
* four engine-emitted aggregate events:
    - ``asyncio.queue.metrics.updated`` — debounced periodic snapshot
    - ``asyncio.queue.pressure.changed`` — pressure level transition
    - ``asyncio.queue.contention.detected`` — blocked producers/consumers
    - ``asyncio.queue.saturation.detected`` — occupancy crossed threshold

Replay semantics:

* :meth:`apply_event` is the single processing entry point. Both the
  live ``bus.subscribe`` callback and the replay rebuild path call it.
* :meth:`rebuild_from_events` resets every aggregate then re-applies a
  deterministic event stream — yielding bit-identical aggregates for
  identical inputs.
* The decision to *emit* an aggregate event lives behind a feature gate
  (``emit_during_apply``), so a rebuild can run silently while the live
  path emits.

Safety:

* All emissions are wrapped in try/except — a bug here cannot break
  queue instrumentation.
* The engine never re-publishes a metrics event onto the bus from
  inside the metrics-event subscriber path (it only subscribes to
  raw queue events, not its own).
* A per-engine threading lock guards the state map + counters.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from typing import Any

from asyncviz.instrumentation.queue.metrics.queue_metrics_configuration import (
    DEFAULT_QUEUE_METRICS_CONFIG,
    QueueMetricsConfig,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    QueueMetricsDelta,
    QueueMetricsEngineSelfSnapshot,
    QueueMetricsRecord,
    QueueMetricsSnapshot,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_observability import (
    get_queue_metrics_engine_metrics,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_state import (
    ApplyOutcome,
    QueueAggregateState,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_tracing import (
    record_queue_metrics_trace,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models.queue import (
    QUEUE_EVENT_TYPES,
    QueueCancelledEvent,
    QueueCreatedEvent,
    QueueEmptyWaitEvent,
    QueueFullWaitEvent,
    QueueGetEvent,
    QueuePutEvent,
    QueueTaskDoneEvent,
)
from asyncviz.runtime.events.models.queue_metrics import (
    QueueContentionDetectedEvent,
    QueueMetricsUpdatedEvent,
    QueuePressureChangedEvent,
    QueueSaturationDetectedEvent,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("instrumentation.queue.metrics.engine")


DeltaListener = Callable[[QueueMetricsDelta], None]


_KNOWN_QUEUE_EVENT_TYPES = (
    QueueCreatedEvent,
    QueuePutEvent,
    QueueGetEvent,
    QueueFullWaitEvent,
    QueueEmptyWaitEvent,
    QueueTaskDoneEvent,
    QueueCancelledEvent,
)


class QueueMetricsEngine:
    """Authoritative queue analytics engine."""

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        config: QueueMetricsConfig = DEFAULT_QUEUE_METRICS_CONFIG,
        emit_during_apply: bool = True,
    ) -> None:
        self._bus = bus
        self._config = config
        self._emit_during_apply = emit_during_apply
        self._lock = threading.RLock()
        self._states: dict[str, QueueAggregateState] = {}
        self._subscription_id_counter = 0
        self._subscriptions: dict[int, DeltaListener] = {}
        self._bus_subscription: object | None = None
        self._self_metrics = get_queue_metrics_engine_metrics()
        self._started = False

    # ── public lifecycle ──────────────────────────────────────────────

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def bus(self) -> EventBus | None:
        return self._bus

    @property
    def config(self) -> QueueMetricsConfig:
        return self._config

    def set_bus(self, bus: EventBus | None) -> None:
        """Late-bind / unbind the event bus. Stops the active subscription
        if the engine was already started."""
        with self._lock:
            if self._started:
                self.stop()
            self._bus = bus

    def start(self) -> None:
        """Subscribe to the bus's raw queue events. Idempotent."""
        with self._lock:
            if self._started:
                return
            if self._bus is None:
                self._started = True
                return
            self._bus_subscription = self._bus.subscribe(
                self._on_bus_event,
                event_types=set(QUEUE_EVENT_TYPES),
            )
            self._started = True

    def stop(self) -> None:
        """Unsubscribe from the bus. Idempotent. State + counters preserved
        so a follow-up :meth:`snapshot` still returns the last view."""
        with self._lock:
            if not self._started:
                return
            sub = self._bus_subscription
            self._bus_subscription = None
            self._started = False
        if sub is not None and self._bus is not None:
            try:
                self._bus.unsubscribe(sub)  # type: ignore[arg-type]
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug("queue metrics engine unsubscribe failed: %s", exc)

    # ── delta subscription ───────────────────────────────────────────

    def subscribe(self, listener: DeltaListener) -> int:
        with self._lock:
            self._subscription_id_counter += 1
            sub_id = self._subscription_id_counter
            self._subscriptions[sub_id] = listener
            return sub_id

    def unsubscribe(self, subscription_id: int) -> bool:
        with self._lock:
            return self._subscriptions.pop(subscription_id, None) is not None

    # ── event ingestion ──────────────────────────────────────────────

    def apply_event(
        self,
        event: RuntimeEvent,
        *,
        emit: bool | None = None,
    ) -> bool:
        """Update per-queue state from ``event``.

        Returns ``True`` if the event was a known queue event and was
        applied to state. ``emit`` overrides the engine-level
        ``emit_during_apply`` flag — pass ``False`` for silent rebuilds.
        """
        if not isinstance(event, _KNOWN_QUEUE_EVENT_TYPES):
            self._self_metrics.record_ignored()
            return False

        queue_id = getattr(event, "queue_id", None)
        if not isinstance(queue_id, str) or not queue_id:
            self._self_metrics.record_ignored()
            return False

        with self._lock:
            state = self._states.get(queue_id)
            if state is None:
                if len(self._states) >= self._config.max_tracked_queues:
                    self._self_metrics.record_queue_evicted()
                    record_queue_metrics_trace("queue-evicted", queue_id)
                    return False
                state = QueueAggregateState(
                    queue_id=queue_id,
                    queue_kind=getattr(event, "queue_kind", "unknown") or "unknown",
                    maxsize=int(getattr(event, "maxsize", 0) or 0),
                    config=self._config,
                )
                self._states[queue_id] = state
                self._self_metrics.set_tracked_queues(len(self._states))

            monotonic_seconds = float(event.monotonic_ns) / 1_000_000_000
            outcome = state.apply_event(event, monotonic_seconds=monotonic_seconds)

        if not outcome.accepted:
            self._self_metrics.record_dropped()
            return False
        self._self_metrics.record_observed()
        record_queue_metrics_trace("event-applied", queue_id)

        should_emit = self._emit_during_apply if emit is None else emit
        if should_emit:
            self._maybe_emit(state, event, outcome, monotonic_seconds)
        return True

    def rebuild_from_events(self, events: Iterable[RuntimeEvent]) -> int:
        """Reset every aggregate then re-apply ``events`` silently.

        Returns the number of events actually applied. Used by the replay
        layer to reconstruct metrics state from a saved event stream.
        """
        with self._lock:
            for state in self._states.values():
                state.finalize()
            self._states.clear()
            self._self_metrics.set_tracked_queues(0)
        applied = 0
        for event in events:
            if self.apply_event(event, emit=False):
                applied += 1
        return applied

    # ── snapshots ─────────────────────────────────────────────────────

    def snapshot_queue(self, queue_id: str) -> QueueMetricsRecord | None:
        with self._lock:
            state = self._states.get(queue_id)
            if state is None:
                return None
            return state.snapshot()

    def snapshot(self) -> QueueMetricsSnapshot:
        with self._lock:
            records = tuple(
                state.snapshot() for state in self._states.values() if not state.finalized
            )
            return QueueMetricsSnapshot(
                queues=records,
                self_metrics=self._self_metrics.snapshot(),
                config=_config_to_dict(self._config),
            )

    def self_snapshot(self) -> QueueMetricsEngineSelfSnapshot:
        return self._self_metrics.snapshot()

    # ── internals ─────────────────────────────────────────────────────

    def _on_bus_event(self, event: RuntimeEvent) -> None:
        # The bus dispatches subscriber callbacks synchronously; any
        # exception we leak crashes the dispatcher. Defensive guard.
        try:
            self.apply_event(event)
        except Exception as exc:  # pragma: no cover — defensive
            self._self_metrics.record_dropped()
            logger.debug("queue metrics engine apply failed: %s", exc)

    def _maybe_emit(
        self,
        state: QueueAggregateState,
        event: RuntimeEvent,
        outcome: ApplyOutcome,
        monotonic_seconds: float,
    ) -> None:
        # Build the snapshot once; multiple emit paths reuse it.
        record = state.snapshot(monotonic_seconds=monotonic_seconds)

        # Pressure level transition (priority — never debounced).
        previous_level = self._infer_previous_level(state, record)
        if previous_level != record.pressure.level:
            self._self_metrics.record_pressure_transition()
            self._emit_delta(
                QueueMetricsDelta(
                    kind="pressure-changed",
                    queue_id=state.queue_id,
                    record=record,
                    previous_level=previous_level,
                    new_level=record.pressure.level,
                ),
            )
            if self._config.emit_pressure:
                self._publish(
                    QueuePressureChangedEvent(
                        queue_id=state.queue_id,
                        queue_kind=state.queue_kind,
                        maxsize=state.maxsize,
                        sequence=state.revision,
                        snapshot=record.to_dict(),
                        previous_level=previous_level,
                        new_level=record.pressure.level,
                        pressure_score=record.pressure.pressure_score,
                        occupancy_ratio=record.occupancy.occupancy_ratio,
                        blocked_producers=record.contention.blocked_producers,
                        blocked_consumers=record.contention.blocked_consumers,
                    ),
                )
            record_queue_metrics_trace(
                "pressure-changed",
                f"{state.queue_id} {previous_level}→{record.pressure.level}",
            )

        # Contention edge.
        if outcome.blocked_transitioned and self._config.emit_contention:
            self._self_metrics.record_contention_detected()
            self._publish(
                QueueContentionDetectedEvent(
                    queue_id=state.queue_id,
                    queue_kind=state.queue_kind,
                    maxsize=state.maxsize,
                    sequence=state.revision,
                    snapshot=record.to_dict(),
                    blocked_producers=record.contention.blocked_producers,
                    blocked_consumers=record.contention.blocked_consumers,
                    blocked_put_total=record.contention.blocked_put_count,
                    blocked_get_total=record.contention.blocked_get_count,
                    contention_kind=outcome.contention_kind,  # type: ignore[arg-type]
                ),
            )
            self._emit_delta(
                QueueMetricsDelta(
                    kind="contention-detected",
                    queue_id=state.queue_id,
                    record=record,
                ),
            )
            record_queue_metrics_trace("contention-detected", state.queue_id)

        # Saturation crossing — both directions noted but only entry
        # emits an event (exits re-arm silently).
        if outcome.saturation_entered and self._config.emit_saturation:
            self._self_metrics.record_saturation_detected()
            self._publish(
                QueueSaturationDetectedEvent(
                    queue_id=state.queue_id,
                    queue_kind=state.queue_kind,
                    maxsize=state.maxsize,
                    sequence=state.revision,
                    snapshot=record.to_dict(),
                    occupancy_ratio=record.occupancy.occupancy_ratio,
                    current_size=record.occupancy.current_size,
                    threshold=self._config.saturation_threshold,
                ),
            )
            self._emit_delta(
                QueueMetricsDelta(
                    kind="saturation-detected",
                    queue_id=state.queue_id,
                    record=record,
                ),
            )
            record_queue_metrics_trace("saturation-detected", state.queue_id)

        # Debounced periodic update.
        if self._config.emit_updated and self._should_emit_update(state, monotonic_seconds):
            self._self_metrics.record_update_emitted()
            state.mark_emitted(monotonic_seconds=monotonic_seconds)
            self._publish(
                QueueMetricsUpdatedEvent(
                    queue_id=state.queue_id,
                    queue_kind=state.queue_kind,
                    maxsize=state.maxsize,
                    sequence=state.revision,
                    snapshot=record.to_dict(),
                    current_size=record.occupancy.current_size,
                    peak_size=record.occupancy.peak_size,
                    occupancy_ratio=record.occupancy.occupancy_ratio,
                    mean_occupancy=record.occupancy.mean_occupancy,
                    put_rate=record.throughput.put_rate,
                    get_rate=record.throughput.get_rate,
                    put_count=record.throughput.put_count,
                    get_count=record.throughput.get_count,
                    producer_consumer_delta=record.throughput.producer_consumer_delta,
                    blocked_producers=record.contention.blocked_producers,
                    blocked_consumers=record.contention.blocked_consumers,
                    blocked_put_count=record.contention.blocked_put_count,
                    blocked_get_count=record.contention.blocked_get_count,
                    cancelled_count=record.contention.cancelled_count,
                    pressure_score=record.pressure.pressure_score,
                    pressure_level=record.pressure.level,
                ),
            )
            self._emit_delta(
                QueueMetricsDelta(
                    kind="updated",
                    queue_id=state.queue_id,
                    record=record,
                ),
            )
            record_queue_metrics_trace("updated-emitted", state.queue_id)

    def _should_emit_update(self, state: QueueAggregateState, monotonic_seconds: float) -> bool:
        if state.last_emit_monotonic == 0.0:
            return True  # always fire the first update for a queue
        elapsed = monotonic_seconds - state.last_emit_monotonic
        if elapsed >= self._config.updated_min_interval_seconds:
            return True
        delta_events = state.revision - state.last_emitted_revision
        return delta_events >= self._config.updated_min_event_delta

    def _infer_previous_level(
        self,
        state: QueueAggregateState,
        record: QueueMetricsRecord,
    ) -> str:
        # The scorer's classification already wrote ``state.pressure.level``
        # via ``evaluate``; what we want here is the level the *previous*
        # snapshot showed. We track the last emitted level on the state.
        return state.last_emitted_level

    def _emit_delta(self, delta: QueueMetricsDelta) -> None:
        # Update the state's "last emitted level" so the next call to
        # ``_infer_previous_level`` reflects this transition.
        state = self._states.get(delta.queue_id)
        if state is not None:
            state.last_emitted_level = delta.record.pressure.level
        for listener in list(self._subscriptions.values()):
            try:
                listener(delta)
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug("queue metrics delta listener failed: %s", exc)

    def _publish(self, event: RuntimeEvent) -> None:
        if self._bus is None:
            return
        try:
            self._bus.publish(event)
        except Exception as exc:  # pragma: no cover — defensive
            self._self_metrics.record_dropped()
            logger.debug("queue metrics publish failed: %s", exc)


def _config_to_dict(config: QueueMetricsConfig) -> dict[str, Any]:
    return {
        "throughput_window_seconds": config.throughput_window_seconds,
        "occupancy_window_size": config.occupancy_window_size,
        "wait_reservoir_size": config.wait_reservoir_size,
        "pressure_warning_threshold": config.pressure_warning_threshold,
        "pressure_critical_threshold": config.pressure_critical_threshold,
        "pressure_hysteresis": config.pressure_hysteresis,
        "saturation_threshold": config.saturation_threshold,
        "saturation_recovery_threshold": config.saturation_recovery_threshold,
        "contention_blocked_threshold": config.contention_blocked_threshold,
        "max_tracked_queues": config.max_tracked_queues,
        "updated_min_interval_seconds": config.updated_min_interval_seconds,
        "updated_min_event_delta": config.updated_min_event_delta,
        "emit_updated": config.emit_updated,
        "emit_pressure": config.emit_pressure,
        "emit_contention": config.emit_contention,
        "emit_saturation": config.emit_saturation,
    }
