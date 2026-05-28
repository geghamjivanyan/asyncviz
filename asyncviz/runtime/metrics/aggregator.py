from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.metrics.counters import CounterSet
from asyncviz.runtime.metrics.durations import DurationAggregator
from asyncviz.runtime.metrics.models import RuntimeMetricsAggregateSnapshot
from asyncviz.runtime.metrics.normalization import MetricsIntent, normalize
from asyncviz.runtime.metrics.queries import MetricsQueryService
from asyncviz.runtime.metrics.rates import RateMeter
from asyncviz.runtime.metrics.reducers import apply_lifecycle
from asyncviz.runtime.metrics.snapshots import build_aggregate_snapshot
from asyncviz.runtime.metrics.streaming import (
    MetricsDelta,
    MetricsListener,
    MetricsSubscription,
    MetricsSubscriptionRegistry,
)
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.runtime.state import RuntimeStateStore, StateChange
    from asyncviz.runtime.timeline import TimelineSegmentEngine

logger = get_logger("runtime.metrics.aggregator")


@dataclass(frozen=True, slots=True)
class AggregatorSelfMetricsSnapshot:
    """Per-aggregator self-metrics view."""

    events_observed: int
    events_stale: int
    events_duplicate: int
    snapshots_emitted: int
    rebuilds_completed: int
    subscription_dispatches: int
    subscription_failures: int
    last_event_sequence: int


class _SelfMetrics:
    __slots__ = (
        "_dedupe_window",
        "_dispatch_failures",
        "_duplicate",
        "_last_event_sequence",
        "_lock",
        "_observed",
        "_rebuilds",
        "_seen_event_ids",
        "_seen_order",
        "_snapshots",
        "_stale",
        "_subscription_dispatches",
    )

    def __init__(self, *, dedupe_window: int = 4096) -> None:
        self._lock = threading.Lock()
        self._observed = 0
        self._stale = 0
        self._duplicate = 0
        self._snapshots = 0
        self._rebuilds = 0
        self._subscription_dispatches = 0
        self._dispatch_failures = 0
        self._last_event_sequence = 0
        self._seen_event_ids: set[str] = set()
        self._seen_order: list[str] = []
        self._dedupe_window = dedupe_window

    def is_duplicate(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._seen_event_ids

    def record_observed(self, *, sequence: int | None, event_id: str) -> None:
        with self._lock:
            self._observed += 1
            if sequence is not None and sequence > self._last_event_sequence:
                self._last_event_sequence = sequence
            self._seen_event_ids.add(event_id)
            self._seen_order.append(event_id)
            if len(self._seen_order) > self._dedupe_window:
                old = self._seen_order.pop(0)
                self._seen_event_ids.discard(old)

    def record_stale(self) -> None:
        with self._lock:
            self._stale += 1

    def record_duplicate(self) -> None:
        with self._lock:
            self._duplicate += 1

    def record_snapshot(self) -> None:
        with self._lock:
            self._snapshots += 1

    def record_rebuild(self) -> None:
        with self._lock:
            self._rebuilds += 1

    def record_dispatch(self, *, failures: int) -> None:
        with self._lock:
            self._subscription_dispatches += 1
            self._dispatch_failures += failures

    def reset(self) -> None:
        with self._lock:
            self._observed = 0
            self._stale = 0
            self._duplicate = 0
            self._last_event_sequence = 0
            self._seen_event_ids.clear()
            self._seen_order.clear()
            # ``snapshots`` / ``rebuilds`` / ``subscription_*`` survive — lifetime counters.

    @property
    def dedupe_window(self) -> int:
        return self._dedupe_window

    def snapshot(self) -> AggregatorSelfMetricsSnapshot:
        with self._lock:
            return AggregatorSelfMetricsSnapshot(
                events_observed=self._observed,
                events_stale=self._stale,
                events_duplicate=self._duplicate,
                snapshots_emitted=self._snapshots,
                rebuilds_completed=self._rebuilds,
                subscription_dispatches=self._subscription_dispatches,
                subscription_failures=self._dispatch_failures,
                last_event_sequence=self._last_event_sequence,
            )


class RuntimeMetricsAggregator:
    """Canonical analytics aggregator for an AsyncViz runtime.

    Subscribes to :class:`RuntimeStateStore` notifications and incrementally
    maintains:

    * Lifecycle counters (``total`` / ``active`` / ``completed`` / ...).
    * Duration aggregators (running stats + reservoir histogram per
      terminal bucket).
    * Throughput rate meters (tasks / completions / cancellations / failures).
    * Cancellation-origin counters.

    Snapshots are derived on demand from these primitives plus the live
    :class:`TaskRegistry` (for lineage / coroutine rollups) and the optional
    :class:`TimelineSegmentEngine` (for segment-level summaries).

    Subscriptions emit :class:`MetricsDelta` records after every successful
    apply, so live charts can update incrementally without polling.
    """

    def __init__(
        self,
        registry: TaskRegistry,
        *,
        clock: RuntimeClock | None = None,
        timeline_engine: TimelineSegmentEngine | None = None,
        rate_window_seconds: int = 30,
        histogram_capacity: int = 2048,
        histogram_seed: int | None = None,
    ) -> None:
        self._registry = registry
        self._clock = clock or get_runtime_clock()
        self._timeline_engine = timeline_engine
        self._lock = threading.RLock()
        self._last_sequence = 0

        self._counts = CounterSet()
        self._cancellations_by_origin = CounterSet()
        self._coroutine_counts = CounterSet()

        self._completed_durations = DurationAggregator(
            capacity=histogram_capacity, seed=histogram_seed
        )
        self._cancelled_durations = DurationAggregator(
            capacity=histogram_capacity, seed=histogram_seed
        )
        self._failed_durations = DurationAggregator(
            capacity=histogram_capacity, seed=histogram_seed
        )
        self._overall_durations = DurationAggregator(
            capacity=histogram_capacity, seed=histogram_seed
        )

        self._rate_meters: dict[str, RateMeter] = {
            "tasks": RateMeter(window_seconds=rate_window_seconds),
            "completions": RateMeter(window_seconds=rate_window_seconds),
            "cancellations": RateMeter(window_seconds=rate_window_seconds),
            "failures": RateMeter(window_seconds=rate_window_seconds),
        }

        self._subscriptions = MetricsSubscriptionRegistry()
        self._self_metrics = _SelfMetrics()
        self._queries = MetricsQueryService(self, registry)

    # ── properties ───────────────────────────────────────────────────────
    @property
    def clock(self) -> RuntimeClock:
        return self._clock

    @property
    def registry(self) -> TaskRegistry:
        return self._registry

    @property
    def timeline_engine(self) -> TimelineSegmentEngine | None:
        return self._timeline_engine

    @property
    def queries(self) -> MetricsQueryService:
        return self._queries

    @property
    def last_sequence(self) -> int:
        with self._lock:
            return self._last_sequence

    @property
    def cancellations_by_origin(self) -> CounterSet:
        return self._cancellations_by_origin

    @property
    def completed_durations(self) -> DurationAggregator:
        return self._completed_durations

    @property
    def cancelled_durations(self) -> DurationAggregator:
        return self._cancelled_durations

    @property
    def failed_durations(self) -> DurationAggregator:
        return self._failed_durations

    @property
    def overall_durations(self) -> DurationAggregator:
        return self._overall_durations

    def counts_snapshot(self) -> dict[str, int]:
        return self._counts.snapshot()

    def rate_meter(self, name: str) -> RateMeter:
        return self._rate_meters[name]

    def self_metrics_snapshot(self) -> AggregatorSelfMetricsSnapshot:
        return self._self_metrics.snapshot()

    # ── apply ────────────────────────────────────────────────────────────
    def apply_event(self, event: RuntimeEvent, *, sequence: int | None = None) -> bool:
        """Update aggregations from one runtime event. Returns whether it applied."""
        norm = normalize(event, sequence=sequence)
        if norm.intent is MetricsIntent.IGNORE:
            return False

        with self._lock:
            if self._self_metrics.is_duplicate(norm.event_id):
                self._self_metrics.record_duplicate()
                return False
            if sequence is not None and sequence <= self._last_sequence:
                self._self_metrics.record_stale()
                return False

            outcome = apply_lifecycle(
                norm,
                counts=self._counts,
                cancellations_by_origin=self._cancellations_by_origin,
                coroutine_counts=self._coroutine_counts,
                completed_durations=self._completed_durations,
                cancelled_durations=self._cancelled_durations,
                failed_durations=self._failed_durations,
                overall_durations=self._overall_durations,
            )

            # Rate meters use monotonic seconds — derive from the event's
            # ``monotonic_ns`` so replays produce deterministic rates.
            monotonic_seconds = event.monotonic_ns / 1_000_000_000
            if norm.intent is MetricsIntent.CREATE:
                self._rate_meters["tasks"].observe(monotonic_seconds=monotonic_seconds)
            elif norm.intent is MetricsIntent.COMPLETE:
                self._rate_meters["completions"].observe(monotonic_seconds=monotonic_seconds)
            elif norm.intent is MetricsIntent.CANCEL:
                self._rate_meters["cancellations"].observe(monotonic_seconds=monotonic_seconds)
            elif norm.intent is MetricsIntent.FAIL:
                self._rate_meters["failures"].observe(monotonic_seconds=monotonic_seconds)

            self._self_metrics.record_observed(sequence=norm.sequence, event_id=norm.event_id)
            if sequence is not None and sequence > self._last_sequence:
                self._last_sequence = sequence

            delta = MetricsDelta(
                event=event,
                sequence=norm.sequence,
                last_sequence=self._last_sequence,
                changes=outcome.changes,
                duration_added_seconds=outcome.duration_added_seconds,
                coroutine_name=norm.coroutine_name,
                terminal_state=outcome.terminal_state,
            )
        self._notify(delta)
        return True

    def apply_state_change(self, change: StateChange) -> bool:
        """Convenience for state-store binding."""
        return self.apply_event(change.event, sequence=change.sequence)

    # ── subscriptions ────────────────────────────────────────────────────
    def subscribe(self, listener: MetricsListener) -> MetricsSubscription:
        return self._subscriptions.add(listener)

    def unsubscribe(self, subscription: MetricsSubscription | int) -> bool:
        return self._subscriptions.remove(subscription)

    def bind(self, store: RuntimeStateStore):
        """Subscribe to ``store``'s state-change stream. Returns the handle."""
        return store.subscribe(self.apply_state_change)

    # ── snapshots ────────────────────────────────────────────────────────
    def snapshot(self) -> RuntimeMetricsAggregateSnapshot:
        with self._lock:
            # Increment first so the embedded count reflects "this is the
            # Nth snapshot" rather than "before this snapshot was built".
            self._self_metrics.record_snapshot()
            return build_aggregate_snapshot(
                self,
                self._registry,
                self._clock,
                timeline_engine=self._timeline_engine,
            )

    # ── rebuild ──────────────────────────────────────────────────────────
    def rebuild(
        self,
        events_with_sequences: Iterable[tuple[RuntimeEvent, int | None]] = (),
    ) -> int:
        """Reset every aggregator and replay ``events_with_sequences``.

        Lifetime counters (``snapshots_emitted``, ``rebuilds_completed``,
        ``subscription_*``) survive the rebuild so they reflect the
        aggregator instance's whole history.
        """
        with self._lock:
            self._counts.reset()
            self._cancellations_by_origin.reset()
            self._coroutine_counts.reset()
            self._completed_durations.reset()
            self._cancelled_durations.reset()
            self._failed_durations.reset()
            self._overall_durations.reset()
            for meter in self._rate_meters.values():
                meter.reset()
            self._self_metrics.reset()
            self._last_sequence = 0

        applied = 0
        for event, sequence in events_with_sequences:
            if self.apply_event(event, sequence=sequence):
                applied += 1

        self._self_metrics.record_rebuild()
        return applied

    # ── internals ────────────────────────────────────────────────────────
    def _notify(self, delta: MetricsDelta) -> None:
        failures = 0
        for sub in self._subscriptions.listeners():
            try:
                sub.listener(delta)
            except Exception as exc:
                failures += 1
                logger.warning(
                    "metrics aggregator subscriber %d failed on %r: %s",
                    sub.id,
                    delta.event.event_type,
                    exc,
                )
        self._self_metrics.record_dispatch(failures=failures)
