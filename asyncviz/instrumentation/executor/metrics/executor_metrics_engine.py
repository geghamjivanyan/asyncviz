"""Canonical executor metrics engine.

Subscribes to the 6 raw executor events on the bus and aggregates
them into per-executor utilization / throughput / saturation
analytics, emitting 4 engine-level aggregate events:

* ``asyncio.executor.metrics.updated`` — debounced snapshot.
* ``asyncio.executor.saturation.changed`` — saturation band transition.
* ``asyncio.executor.contention.detected`` — active-worker ratio edge.
* ``asyncio.executor.latency.spike.detected`` — submission-latency spike.

Mirrors the queue + semaphore metrics engines in shape.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from typing import Any

from asyncviz.instrumentation.executor.metrics.executor_metrics_configuration import (
    DEFAULT_EXECUTOR_METRICS_CONFIG,
    ExecutorMetricsConfig,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_models import (
    ExecutorMetricsDelta,
    ExecutorMetricsEngineSelfSnapshot,
    ExecutorMetricsRecord,
    ExecutorMetricsSnapshot,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_observability import (
    get_executor_metrics_engine_metrics,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_state import (
    ApplyOutcome,
    ExecutorAggregateState,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_tracing import (
    record_executor_metrics_trace,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models.executor import (
    EXECUTOR_EVENT_TYPES,
    ExecutorRegisteredEvent,
    ExecutorWorkCancelledEvent,
    ExecutorWorkCompletedEvent,
    ExecutorWorkFailedEvent,
    ExecutorWorkStartedEvent,
    ExecutorWorkSubmittedEvent,
)
from asyncviz.runtime.events.models.executor_metrics import (
    ExecutorContentionDetectedEvent,
    ExecutorLatencySpikeDetectedEvent,
    ExecutorMetricsUpdatedEvent,
    ExecutorSaturationChangedEvent,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("instrumentation.executor.metrics.engine")


DeltaListener = Callable[[ExecutorMetricsDelta], None]


_KNOWN_EVENT_TYPES = (
    ExecutorRegisteredEvent,
    ExecutorWorkSubmittedEvent,
    ExecutorWorkStartedEvent,
    ExecutorWorkCompletedEvent,
    ExecutorWorkFailedEvent,
    ExecutorWorkCancelledEvent,
)


class ExecutorMetricsEngine:
    """Authoritative executor analytics engine."""

    def __init__(
        self,
        *,
        bus: EventBus | None = None,
        config: ExecutorMetricsConfig = DEFAULT_EXECUTOR_METRICS_CONFIG,
        emit_during_apply: bool = True,
    ) -> None:
        self._bus = bus
        self._config = config
        self._emit_during_apply = emit_during_apply
        self._lock = threading.RLock()
        self._states: dict[str, ExecutorAggregateState] = {}
        self._subscription_id_counter = 0
        self._subscriptions: dict[int, DeltaListener] = {}
        self._bus_subscription: object | None = None
        self._self_metrics = get_executor_metrics_engine_metrics()
        self._started = False

    # ── public lifecycle ──────────────────────────────────────────────

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def bus(self) -> EventBus | None:
        return self._bus

    @property
    def config(self) -> ExecutorMetricsConfig:
        return self._config

    def set_bus(self, bus: EventBus | None) -> None:
        with self._lock:
            if self._started:
                self.stop()
            self._bus = bus

    def start(self) -> None:
        """Subscribe to the bus's raw executor events. Idempotent."""
        with self._lock:
            if self._started:
                return
            if self._bus is None:
                self._started = True
                return
            self._bus_subscription = self._bus.subscribe(
                self._on_bus_event,
                event_types=set(EXECUTOR_EVENT_TYPES),
            )
            self._started = True

    def stop(self) -> None:
        """Unsubscribe from the bus. Idempotent. State + counters
        preserved."""
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
                logger.debug("executor metrics engine unsubscribe failed: %s", exc)

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
        if not isinstance(event, _KNOWN_EVENT_TYPES):
            self._self_metrics.record_ignored()
            return False

        executor_id = getattr(event, "executor_id", None)
        if not isinstance(executor_id, str) or not executor_id:
            self._self_metrics.record_ignored()
            return False

        with self._lock:
            state = self._states.get(executor_id)
            if state is None:
                if len(self._states) >= self._config.max_tracked_executors:
                    self._self_metrics.record_executor_evicted()
                    record_executor_metrics_trace("executor-evicted", executor_id)
                    return False
                max_workers = getattr(event, "max_workers", None)
                if not isinstance(max_workers, int) or max_workers <= 0:
                    max_workers = None
                state = ExecutorAggregateState(
                    executor_id=executor_id,
                    executor_kind=getattr(event, "executor_kind", "unknown") or "unknown",
                    max_workers=max_workers,
                    config=self._config,
                )
                self._states[executor_id] = state
                self._self_metrics.set_tracked_executors(len(self._states))

            monotonic_seconds = float(event.monotonic_ns) / 1_000_000_000
            outcome = state.apply_event(event, monotonic_seconds=monotonic_seconds)

        if not outcome.accepted:
            self._self_metrics.record_dropped()
            return False
        self._self_metrics.record_observed()
        record_executor_metrics_trace("event-applied", executor_id)

        should_emit = self._emit_during_apply if emit is None else emit
        if should_emit:
            self._maybe_emit(state, outcome, monotonic_seconds)
        return True

    def rebuild_from_events(self, events: Iterable[RuntimeEvent]) -> int:
        """Reset every aggregate then re-apply ``events`` silently."""
        with self._lock:
            for state in self._states.values():
                state.finalize()
            self._states.clear()
            self._self_metrics.set_tracked_executors(0)
        applied = 0
        for event in events:
            if self.apply_event(event, emit=False):
                applied += 1
        return applied

    # ── snapshots ─────────────────────────────────────────────────────

    def snapshot_executor(self, executor_id: str) -> ExecutorMetricsRecord | None:
        with self._lock:
            state = self._states.get(executor_id)
            if state is None:
                return None
            return state.snapshot()

    def snapshot(self) -> ExecutorMetricsSnapshot:
        with self._lock:
            records = tuple(
                state.snapshot() for state in self._states.values() if not state.finalized
            )
            return ExecutorMetricsSnapshot(
                executors=records,
                self_metrics=self._self_metrics.snapshot(),
                config=_config_to_dict(self._config),
            )

    def self_snapshot(self) -> ExecutorMetricsEngineSelfSnapshot:
        return self._self_metrics.snapshot()

    # ── internals ─────────────────────────────────────────────────────

    def _on_bus_event(self, event: RuntimeEvent) -> None:
        try:
            self.apply_event(event)
        except Exception as exc:  # pragma: no cover — defensive
            self._self_metrics.record_dropped()
            logger.debug("executor metrics engine apply failed: %s", exc)

    def _maybe_emit(
        self,
        state: ExecutorAggregateState,
        outcome: ApplyOutcome,
        monotonic_seconds: float,
    ) -> None:
        record = state.snapshot(monotonic_seconds=monotonic_seconds)

        # Saturation level transition (priority — never debounced).
        if state.last_emitted_level != record.saturation.level:
            previous_level = state.last_emitted_level
            state.last_emitted_level = record.saturation.level
            self._self_metrics.record_saturation_transition()
            self._emit_delta(
                ExecutorMetricsDelta(
                    kind="saturation-changed",
                    executor_id=state.executor_id,
                    record=record,
                    previous_level=previous_level,
                    new_level=record.saturation.level,
                ),
            )
            if self._config.emit_saturation:
                self._publish(
                    ExecutorSaturationChangedEvent(
                        executor_id=state.executor_id,
                        executor_kind=state.executor_kind,
                        max_workers=state.max_workers,
                        sequence=state.revision,
                        snapshot=record.to_dict(),
                        previous_level=previous_level,
                        new_level=record.saturation.level,
                        saturation_score=record.saturation.saturation_score,
                        utilization_ratio=record.utilization.utilization_ratio,
                        backlog=record.throughput.backlog,
                    ),
                )
            record_executor_metrics_trace(
                "saturation-changed",
                f"{state.executor_id} {previous_level}→{record.saturation.level}",
            )

        # Contention edge.
        if outcome.contention_edge and self._config.emit_contention:
            self._self_metrics.record_contention_detected()
            self._publish(
                ExecutorContentionDetectedEvent(
                    executor_id=state.executor_id,
                    executor_kind=state.executor_kind,
                    max_workers=state.max_workers,
                    sequence=state.revision,
                    snapshot=record.to_dict(),
                    active_workers=record.utilization.active_workers,
                    utilization_ratio=record.utilization.utilization_ratio,
                ),
            )
            self._emit_delta(
                ExecutorMetricsDelta(
                    kind="contention-detected",
                    executor_id=state.executor_id,
                    record=record,
                ),
            )
            record_executor_metrics_trace("contention-detected", state.executor_id)

        # Latency spike (with cooldown).
        if (
            outcome.latency_spike
            and self._config.emit_latency_spike
            and state.can_emit_latency_spike(monotonic_seconds=monotonic_seconds)
        ):
            state.mark_latency_spike_emitted(monotonic_seconds=monotonic_seconds)
            self._self_metrics.record_latency_spike()
            self._publish(
                ExecutorLatencySpikeDetectedEvent(
                    executor_id=state.executor_id,
                    executor_kind=state.executor_kind,
                    max_workers=state.max_workers,
                    sequence=state.revision,
                    snapshot=record.to_dict(),
                    submission_latency_seconds=record.submission_latency.max_seconds,
                    threshold_seconds=self._config.latency_spike_threshold_seconds,
                    active_workers=record.utilization.active_workers,
                ),
            )
            self._emit_delta(
                ExecutorMetricsDelta(
                    kind="latency-spike-detected",
                    executor_id=state.executor_id,
                    record=record,
                ),
            )
            record_executor_metrics_trace("latency-spike-detected", state.executor_id)

        # Debounced periodic update.
        if self._config.emit_updated and self._should_emit_update(
            state,
            monotonic_seconds,
        ):
            self._self_metrics.record_update_emitted()
            state.mark_emitted(monotonic_seconds=monotonic_seconds)
            self._publish(
                ExecutorMetricsUpdatedEvent(
                    executor_id=state.executor_id,
                    executor_kind=state.executor_kind,
                    max_workers=state.max_workers,
                    sequence=state.revision,
                    snapshot=record.to_dict(),
                    active_workers=record.utilization.active_workers,
                    peak_active_workers=record.utilization.peak_active_workers,
                    utilization_ratio=record.utilization.utilization_ratio,
                    mean_utilization=record.utilization.mean_utilization,
                    submissions=record.throughput.submissions,
                    completions=record.throughput.completions,
                    failures=record.throughput.failures,
                    cancellations=record.throughput.cancellations,
                    submission_rate=record.throughput.submission_rate,
                    completion_rate=record.throughput.completion_rate,
                    backlog=record.throughput.backlog,
                    mean_submission_latency_seconds=record.submission_latency.mean_seconds,
                    p95_submission_latency_seconds=record.submission_latency.p95_seconds,
                    mean_execution_duration_seconds=record.execution_duration.mean_seconds,
                    p95_execution_duration_seconds=record.execution_duration.p95_seconds,
                    saturation_score=record.saturation.saturation_score,
                    saturation_level=record.saturation.level,
                ),
            )
            self._emit_delta(
                ExecutorMetricsDelta(
                    kind="updated",
                    executor_id=state.executor_id,
                    record=record,
                ),
            )
            record_executor_metrics_trace("updated-emitted", state.executor_id)

    def _should_emit_update(
        self,
        state: ExecutorAggregateState,
        monotonic_seconds: float,
    ) -> bool:
        if state.last_emit_monotonic == 0.0:
            return True
        elapsed = monotonic_seconds - state.last_emit_monotonic
        if elapsed >= self._config.updated_min_interval_seconds:
            return True
        delta_events = state.revision - state.last_emitted_revision
        return delta_events >= self._config.updated_min_event_delta

    def _emit_delta(self, delta: ExecutorMetricsDelta) -> None:
        for listener in list(self._subscriptions.values()):
            try:
                listener(delta)
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug("executor metrics delta listener failed: %s", exc)

    def _publish(self, event: RuntimeEvent) -> None:
        if self._bus is None:
            return
        try:
            self._bus.publish(event)
        except Exception as exc:  # pragma: no cover — defensive
            self._self_metrics.record_dropped()
            logger.debug("executor metrics publish failed: %s", exc)


def _config_to_dict(config: ExecutorMetricsConfig) -> dict[str, Any]:
    return {
        "throughput_window_seconds": config.throughput_window_seconds,
        "utilization_window_size": config.utilization_window_size,
        "latency_reservoir_size": config.latency_reservoir_size,
        "saturation_warning_threshold": config.saturation_warning_threshold,
        "saturation_critical_threshold": config.saturation_critical_threshold,
        "saturation_hysteresis": config.saturation_hysteresis,
        "contention_active_worker_ratio": config.contention_active_worker_ratio,
        "latency_spike_threshold_seconds": config.latency_spike_threshold_seconds,
        "latency_spike_min_interval_seconds": config.latency_spike_min_interval_seconds,
        "max_tracked_executors": config.max_tracked_executors,
        "updated_min_interval_seconds": config.updated_min_interval_seconds,
        "updated_min_event_delta": config.updated_min_event_delta,
        "emit_updated": config.emit_updated,
        "emit_saturation": config.emit_saturation,
        "emit_contention": config.emit_contention,
        "emit_latency_spike": config.emit_latency_spike,
    }
