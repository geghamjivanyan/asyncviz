from __future__ import annotations

import threading
from collections.abc import Iterable
from typing import TYPE_CHECKING

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.lineage import LineageTracker
from asyncviz.runtime.state.metrics import StateStoreMetrics, StateStoreMetricsSnapshot
from asyncviz.runtime.state.models import RuntimeStateSnapshot
from asyncviz.runtime.state.normalization import normalize_event
from asyncviz.runtime.state.queries import StateQueryService
from asyncviz.runtime.state.reconciliation import (
    ReconciliationDecision,
    ReconciliationPolicy,
)
from asyncviz.runtime.state.reducers import (
    ProjectionInvalidationBus,
    ReducerContext,
    ReducerMetrics,
    ReducerMetricsSnapshot,
    ReducerRegistry,
    TransitionHistory,
    build_default_registry,
)
from asyncviz.runtime.state.snapshots import build_runtime_snapshot
from asyncviz.runtime.state.subscriptions import (
    StateChange,
    StateListener,
    StateSubscription,
    StateSubscriptionRegistry,
)
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.runtime.queue import QueuedEvent

logger = get_logger("runtime.state.store")


class RuntimeStateStore:
    """Canonical derived-state model for an AsyncViz runtime.

    Sits *above* the registry / lineage tracker. The store owns:

    * **Reconciliation** — sequence-aware dedup and stale-event filtering.
    * **Reducers** — pure dispatch on event class; mutations land on the
      registry, which is the structural source of truth.
    * **Snapshots** — composes registry + lineage + projections into a
      single replay-safe Pydantic value.
    * **Subscriptions** — synchronous notifications after every successful
      apply, intended for view layers and analytics.
    * **Metrics** — applied / stale / duplicate / unknown counters plus the
      last-event high-water marks.

    The store is *not* the event transport. It receives events through
    :meth:`apply`; the dashboard's lifespan wires it to the bus via
    :func:`asyncviz.runtime.state.lifecycle.bind_store_to_event_bus`. Tests
    drive ``apply()`` directly.
    """

    def __init__(
        self,
        registry: TaskRegistry,
        *,
        clock: RuntimeClock | None = None,
        policy: ReconciliationPolicy | None = None,
        reducer_registry: ReducerRegistry | None = None,
        history: TransitionHistory | None = None,
    ) -> None:
        self._registry = registry
        self._lineage: LineageTracker = registry.lineage
        self._clock = clock or get_runtime_clock()
        self._policy = policy or ReconciliationPolicy()
        self._metrics = StateStoreMetrics()
        self._reducer_registry = reducer_registry or build_default_registry()
        self._history = history or TransitionHistory()
        self._projections = ProjectionInvalidationBus()
        self._reducer_metrics = ReducerMetrics()
        self._subscriptions = StateSubscriptionRegistry()
        self._queries = StateQueryService(registry, registry.lineage)
        self._lock = threading.RLock()

    # ── properties ───────────────────────────────────────────────────────
    @property
    def registry(self) -> TaskRegistry:
        return self._registry

    @property
    def lineage(self) -> LineageTracker:
        return self._lineage

    @property
    def clock(self) -> RuntimeClock:
        return self._clock

    @property
    def queries(self) -> StateQueryService:
        return self._queries

    @property
    def history(self) -> TransitionHistory:
        return self._history

    @property
    def projection_invalidations(self) -> ProjectionInvalidationBus:
        return self._projections

    @property
    def reducer_registry(self) -> ReducerRegistry:
        return self._reducer_registry

    @property
    def last_sequence(self) -> int:
        with self._lock:
            return self._policy.last_sequence

    # ── apply path ───────────────────────────────────────────────────────
    def apply(self, event: RuntimeEvent, *, sequence: int | None = None) -> ReconciliationDecision:
        """Apply ``event`` to the store. Returns the reconciliation outcome.

        ``sequence`` is the queue-allocated sequence number. ``None`` means
        the caller doesn't know — duplicate detection still works via
        ``event_id`` but stale filtering is skipped. The dashboard wires
        this through automatically when the store is hooked into the queue's
        post-dispatch slot.
        """
        normalized = normalize_event(event, sequence=sequence)
        with self._lock:
            decision = self._policy.evaluate(
                sequence=normalized.sequence,
                event_id=normalized.event_id,
            )
            if decision is ReconciliationDecision.STALE:
                self._metrics.record_stale()
                return decision
            if decision is ReconciliationDecision.DUPLICATE:
                self._metrics.record_duplicate()
                return decision

            if not normalized.is_task_event:
                # Non-task events (warnings, metrics, future taxonomy) flow
                # through the store for observability but don't mutate state.
                self._metrics.record_unknown_type()
                self._policy.record_applied(
                    sequence=normalized.sequence,
                    event_id=normalized.event_id,
                )
                self._notify(
                    StateChange(
                        event=event,
                        sequence=normalized.sequence,
                        last_sequence=self._policy.last_sequence,
                        decision=decision.value,
                        event_type=normalized.event_type,
                        event_id=normalized.event_id,
                    )
                )
                return decision

            reducer = self._reducer_registry.get(event)
            if reducer is None:
                # Task event without a reducer (shouldn't happen — but stay
                # defensive). Account for it as rejected so the metric
                # surfaces the drift.
                self._metrics.record_rejected()
                return ReconciliationDecision.STALE  # treat as no-op

            ctx = ReducerContext(
                registry=self._registry,
                history=self._history,
                projections=self._projections,
                metrics=self._reducer_metrics,
                sequence=normalized.sequence,
            )
            try:
                result = reducer.apply(ctx, event)
            except Exception as exc:
                self._metrics.record_rejected()
                logger.warning(
                    "state store reducer %r raised for %r: %s",
                    reducer.name,
                    normalized.event_type,
                    exc,
                )
                return ReconciliationDecision.STALE

            if not result.applied:
                # Reducer cleanly rejected (invalid transition, terminal lock,
                # etc.). Surface it as a store-level rejection so the apply
                # counter stays accurate.
                self._metrics.record_rejected()
                logger.debug(
                    "reducer %r rejected %r: %s",
                    reducer.name,
                    normalized.event_type,
                    result.reason,
                )
                # Don't advance the policy high-water mark — a future event
                # with the same sequence should be allowed to retry, and a
                # subsequent stale check is still meaningful.
                return ReconciliationDecision.STALE

            self._policy.record_applied(
                sequence=normalized.sequence,
                event_id=normalized.event_id,
            )
            self._metrics.record_applied(
                sequence=normalized.sequence or 0,
                monotonic_ns=event.monotonic_ns,
                event_id=normalized.event_id,
                event_type=normalized.event_type,
            )
            self._notify(
                StateChange(
                    event=event,
                    sequence=normalized.sequence,
                    last_sequence=self._policy.last_sequence,
                    decision=decision.value,
                    event_type=normalized.event_type,
                    event_id=normalized.event_id,
                )
            )
            return decision

    def apply_queued(self, item: QueuedEvent) -> ReconciliationDecision:
        """Convenience: apply a :class:`QueuedEvent` (sequence + event pair)."""
        return self.apply(item.event, sequence=item.sequence)

    # ── snapshots ────────────────────────────────────────────────────────
    def snapshot(
        self,
        *,
        include_projections: bool = True,
        include_transitions: bool = True,
    ) -> RuntimeStateSnapshot:
        with self._lock:
            last_metrics = self._metrics.snapshot()
            snap = build_runtime_snapshot(
                self._registry,
                self._lineage,
                self._clock,
                last_sequence=self._policy.last_sequence,
                last_event_id=last_metrics.last_event_id,
                include_projections=include_projections,
                history=self._history,
                include_transitions=include_transitions,
            )
            self._metrics.record_snapshot()
            return snap

    # ── rebuild ──────────────────────────────────────────────────────────
    def rebuild(self, events: Iterable[RuntimeEvent | QueuedEvent]) -> int:
        """Reset the store and replay ``events`` in order. Returns the apply count.

        Intended for replay tools and reconnect bootstrap. The reconciliation
        policy is reset so stale filtering doesn't fight against the replay's
        natural ordering. The registry is wiped first via :meth:`TaskRegistry.clear`.
        """
        from asyncviz.runtime.queue import QueuedEvent  # local import to avoid cycle

        with self._lock:
            self._registry.clear()
            self._history.clear()
            self._projections.reset()
            self._reducer_metrics.reset()
            self._policy.reset_for_rebuild()
            self._metrics.soft_reset_lifetime()
            applied = 0
            for item in events:
                if isinstance(item, QueuedEvent):
                    decision = self.apply(item.event, sequence=item.sequence)
                else:
                    decision = self.apply(item)
                if decision is ReconciliationDecision.APPLY:
                    applied += 1
            self._metrics.record_rebuild()
            return applied

    # ── subscriptions ────────────────────────────────────────────────────
    def subscribe(self, listener: StateListener) -> StateSubscription:
        return self._subscriptions.add(listener)

    def unsubscribe(self, subscription: StateSubscription | int) -> bool:
        return self._subscriptions.remove(subscription)

    # ── observability ────────────────────────────────────────────────────
    def metrics_snapshot(self) -> StateStoreMetricsSnapshot:
        return self._metrics.snapshot()

    def reducer_metrics_snapshot(self) -> ReducerMetricsSnapshot:
        return self._reducer_metrics.snapshot()

    def transition_history(self, task_id: str) -> tuple[object, ...]:
        """Per-task transition history (closest-first time order)."""
        return self._history.get(task_id)

    def __len__(self) -> int:
        return len(self._registry)

    # ── internals ────────────────────────────────────────────────────────
    def _notify(self, change: StateChange) -> None:
        failures = 0
        for sub in self._subscriptions.listeners():
            try:
                sub.listener(change)
            except Exception as exc:
                failures += 1
                logger.warning(
                    "state store subscriber %d failed on %r: %s",
                    sub.id,
                    change.event_type,
                    exc,
                )
        self._metrics.record_subscription_dispatch(failures=failures)
