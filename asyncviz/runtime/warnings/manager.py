from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.warnings.deduplication import DedupDecision, evaluate_dedup
from asyncviz.runtime.warnings.detectors import (
    DetectorContext,
    WarningDetector,
    default_detectors,
)
from asyncviz.runtime.warnings.exceptions import DetectorRegistrationError
from asyncviz.runtime.warnings.expiration import DEFAULT_TTL_SECONDS, ExpirationPolicy
from asyncviz.runtime.warnings.lifecycle import WarningLifecycle, fresh_warning_id
from asyncviz.runtime.warnings.models import (
    WarningSelfMetricsModel,
    WarningSnapshot,
)
from asyncviz.runtime.warnings.normalization import WarningTrigger
from asyncviz.runtime.warnings.queries import WarningQueryService
from asyncviz.runtime.warnings.snapshots import build_warning_snapshot
from asyncviz.runtime.warnings.streaming import (
    WarningChange,
    WarningDelta,
    WarningListener,
    WarningSubscription,
    WarningSubscriptionRegistry,
)
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.runtime.metrics import RuntimeMetricsAggregator
    from asyncviz.runtime.state import RuntimeStateStore, StateChange
    from asyncviz.runtime.tasks import TaskRegistry

logger = get_logger("runtime.warnings.manager")


@dataclass(slots=True)
class _SelfMetrics:
    """Mutable working-state counters for self-observability."""

    evaluations_run: int = 0
    detector_failures: int = 0
    warnings_emitted: int = 0
    warnings_resolved: int = 0
    warnings_expired: int = 0
    dedup_suppressions: int = 0
    snapshots_emitted: int = 0
    subscription_dispatches: int = 0
    subscription_failures: int = 0
    last_event_sequence: int = 0


class RuntimeWarningManager:
    """Canonical anomaly + runtime-health surface.

    Subscribes to :class:`RuntimeStateStore` notifications and runs the
    registered detectors on every event (and on every snapshot, for the
    aggregate-driven detectors). Maintains per-warning :class:`WarningLifecycle`
    working state with deterministic deduplication and TTL-based expiration.

    Streaming subscribers receive :class:`WarningDelta` notifications on
    every activation / update / resolution / expiration so live dashboards
    can stay current without polling.
    """

    def __init__(
        self,
        registry: TaskRegistry,
        *,
        aggregator: RuntimeMetricsAggregator | None = None,
        clock: RuntimeClock | None = None,
        detectors: Iterable[WarningDetector] | None = None,
        expiration: ExpirationPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._aggregator = aggregator
        self._clock = clock or get_runtime_clock()
        self._lock = threading.RLock()
        self._lifecycles: dict[str, WarningLifecycle] = {}  # keyed by warning_key
        self._by_id: dict[str, WarningLifecycle] = {}
        self._detectors: dict[str, WarningDetector] = {}
        for det in detectors or default_detectors():
            self._register_detector_locked(det)
        self._subscriptions = WarningSubscriptionRegistry()
        self._expiration = expiration or ExpirationPolicy(ttl_seconds=DEFAULT_TTL_SECONDS)
        self._self_metrics = _SelfMetrics()
        self._queries = WarningQueryService(self)
        self._last_sequence = 0

    # ── identity ─────────────────────────────────────────────────────────
    @property
    def clock(self) -> RuntimeClock:
        return self._clock

    @property
    def registry(self) -> TaskRegistry:
        return self._registry

    @property
    def queries(self) -> WarningQueryService:
        return self._queries

    @property
    def detectors(self) -> tuple[WarningDetector, ...]:
        with self._lock:
            return tuple(self._detectors.values())

    @property
    def expiration(self) -> ExpirationPolicy:
        return self._expiration

    @property
    def last_sequence(self) -> int:
        with self._lock:
            return self._last_sequence

    # ── detector registration ────────────────────────────────────────────
    def register_detector(self, detector: WarningDetector) -> None:
        with self._lock:
            self._register_detector_locked(detector)

    def _register_detector_locked(self, detector: WarningDetector) -> None:
        if detector.name in self._detectors:
            raise DetectorRegistrationError(f"detector name {detector.name!r} already registered")
        self._detectors[detector.name] = detector

    def unregister_detector(self, name: str) -> bool:
        with self._lock:
            return self._detectors.pop(name, None) is not None

    # ── apply ────────────────────────────────────────────────────────────
    def apply_event(self, event: RuntimeEvent, *, sequence: int | None = None) -> None:
        """Run event-driven detectors over ``event`` and apply their triggers."""
        with self._lock:
            ctx = DetectorContext(registry=self._registry, aggregator=self._aggregator)
            for detector in self._detectors.values():
                try:
                    triggers = list(detector.evaluate_event(ctx, event, sequence=sequence))
                except Exception as exc:
                    self._self_metrics.detector_failures += 1
                    logger.warning(
                        "warning detector %r failed on event %r: %s",
                        detector.name,
                        event.event_type,
                        exc,
                    )
                    continue
                self._self_metrics.evaluations_run += 1
                for trigger in triggers:
                    self._apply_trigger(trigger)
            if sequence is not None and sequence > self._last_sequence:
                self._last_sequence = sequence
                self._self_metrics.last_event_sequence = sequence

    def evaluate(self, *, monotonic_ns: int | None = None) -> None:
        """Run snapshot-driven detectors against the current state.

        Called by the lifespan on demand (e.g., per heartbeat) so aggregate
        thresholds get checked even when the event stream is quiet.
        """
        with self._lock:
            ts_ns = monotonic_ns if monotonic_ns is not None else self._clock.monotonic_ns()
            wall_seconds = self._clock.now()
            ctx = DetectorContext(registry=self._registry, aggregator=self._aggregator)
            for detector in self._detectors.values():
                try:
                    triggers = list(
                        detector.evaluate_snapshot(
                            ctx,
                            sequence=self._last_sequence,
                            monotonic_ns=ts_ns,
                            wall_seconds=wall_seconds,
                        )
                    )
                except Exception as exc:
                    self._self_metrics.detector_failures += 1
                    logger.warning(
                        "warning detector %r snapshot-evaluation failed: %s",
                        detector.name,
                        exc,
                    )
                    continue
                self._self_metrics.evaluations_run += 1
                fired_keys = set()
                for trigger in triggers:
                    self._apply_trigger(trigger)
                    fired_keys.add(trigger.warning_key)
                # Auto-resolve only applies to *snapshot-driven* detectors —
                # event-driven detectors leave their warnings open until
                # explicit resolution or TTL expiration.
                if getattr(detector, "snapshot_driven", False):
                    for lifecycle in list(self._lifecycles.values()):
                        if (
                            lifecycle.detector == detector.name
                            and not lifecycle.resolved
                            and lifecycle.warning_key not in fired_keys
                        ):
                            self._mark_resolved_internal(
                                lifecycle,
                                sequence=self._last_sequence,
                                monotonic_ns=ts_ns,
                                wall_seconds=wall_seconds,
                            )
            self._sweep_expired(now_monotonic_ns=ts_ns, now_wall=wall_seconds)

    # ── manual control ───────────────────────────────────────────────────
    def resolve_warning(
        self,
        warning_id: str,
        *,
        sequence: int | None = None,
    ) -> bool:
        """Manually resolve ``warning_id``. Returns ``False`` if unknown."""
        with self._lock:
            lifecycle = self._by_id.get(warning_id)
            if lifecycle is None or lifecycle.resolved:
                return False
            self._mark_resolved_internal(
                lifecycle,
                sequence=sequence,
                monotonic_ns=self._clock.monotonic_ns(),
                wall_seconds=self._clock.now(),
            )
            return True

    # ── state-store binding ──────────────────────────────────────────────
    def bind(self, store: RuntimeStateStore):
        """Subscribe to ``store``'s state-change stream. Returns the handle."""

        def listener(change: StateChange) -> None:
            self.apply_event(change.event, sequence=change.sequence)

        return store.subscribe(listener)

    # ── reads ────────────────────────────────────────────────────────────
    def find_by_id(self, warning_id: str) -> WarningLifecycle | None:
        with self._lock:
            return self._by_id.get(warning_id)

    def find_by_key(self, warning_key: str) -> WarningLifecycle | None:
        with self._lock:
            return self._lifecycles.get(warning_key)

    def lifecycles_view(self) -> tuple[WarningLifecycle, ...]:
        with self._lock:
            return tuple(self._lifecycles.values())

    def active_view(self) -> tuple[WarningLifecycle, ...]:
        with self._lock:
            return tuple(w for w in self._lifecycles.values() if not w.resolved)

    def resolved_view(self) -> tuple[WarningLifecycle, ...]:
        with self._lock:
            return tuple(w for w in self._lifecycles.values() if w.resolved)

    # ── subscriptions ────────────────────────────────────────────────────
    def subscribe(self, listener: WarningListener) -> WarningSubscription:
        return self._subscriptions.add(listener)

    def unsubscribe(self, subscription: WarningSubscription | int) -> bool:
        return self._subscriptions.remove(subscription)

    # ── snapshots / observability ────────────────────────────────────────
    def snapshot(self) -> WarningSnapshot:
        with self._lock:
            # Expiration sweep first so the snapshot reflects current truth.
            now_ns = self._clock.monotonic_ns()
            self._sweep_expired(now_monotonic_ns=now_ns, now_wall=self._clock.now())
            self._self_metrics.snapshots_emitted += 1
            self_metrics = self._self_metrics_model()
            return build_warning_snapshot(
                self.active_view(),
                self.resolved_view(),
                self_metrics,
                self._clock,
                last_sequence=self._last_sequence,
            )

    def self_metrics_snapshot(self) -> WarningSelfMetricsModel:
        with self._lock:
            return self._self_metrics_model()

    def _self_metrics_model(self) -> WarningSelfMetricsModel:
        m = self._self_metrics
        return WarningSelfMetricsModel(
            detectors_registered=len(self._detectors),
            evaluations_run=m.evaluations_run,
            detector_failures=m.detector_failures,
            warnings_emitted=m.warnings_emitted,
            warnings_resolved=m.warnings_resolved,
            warnings_expired=m.warnings_expired,
            dedup_suppressions=m.dedup_suppressions,
            snapshots_emitted=m.snapshots_emitted,
            subscription_dispatches=m.subscription_dispatches,
            subscription_failures=m.subscription_failures,
            last_event_sequence=m.last_event_sequence,
        )

    # ── rebuild ──────────────────────────────────────────────────────────
    def rebuild(
        self,
        events_with_sequences: Iterable[tuple[RuntimeEvent, int | None]] = (),
    ) -> int:
        """Reset every working state value and replay events. Returns apply count."""
        with self._lock:
            self._lifecycles.clear()
            self._by_id.clear()
            self._self_metrics = _SelfMetrics()
            self._last_sequence = 0
        count = 0
        for event, sequence in events_with_sequences:
            self.apply_event(event, sequence=sequence)
            count += 1
        return count

    def clear(self) -> None:
        with self._lock:
            self._lifecycles.clear()
            self._by_id.clear()
            self._self_metrics = _SelfMetrics()
            self._last_sequence = 0

    # ── internals ────────────────────────────────────────────────────────
    def _apply_trigger(self, trigger: WarningTrigger) -> None:
        existing = self._lifecycles.get(trigger.warning_key)
        result = evaluate_dedup(
            warning_key=trigger.warning_key,
            existing=existing,
            sequence=trigger.sequence,
        )
        change: WarningChange | None = None
        lifecycle: WarningLifecycle | None = None

        if result.decision is DedupDecision.SUPPRESS:
            self._self_metrics.dedup_suppressions += 1
            return

        if result.decision is DedupDecision.ACTIVATE:
            lifecycle = WarningLifecycle(
                warning_id=fresh_warning_id(),
                warning_key=trigger.warning_key,
                warning_type=trigger.warning_type,
                severity=trigger.severity,
                detector=trigger.detector,
                message=trigger.message,
                created_sequence=trigger.sequence,
                created_monotonic_ns=trigger.monotonic_ns,
                created_at_wall=trigger.wall_seconds,
                last_observed_sequence=trigger.sequence,
                last_observed_monotonic_ns=trigger.monotonic_ns,
                last_observed_wall=trigger.wall_seconds,
                related_task_ids=list(trigger.related_task_ids),
                lineage_root_id=trigger.lineage_root_id,
                metadata=dict(trigger.metadata),
                runtime_id=str(self._clock.runtime_id),
            )
            self._lifecycles[trigger.warning_key] = lifecycle
            self._by_id[lifecycle.warning_id] = lifecycle
            self._self_metrics.warnings_emitted += 1
            change = WarningChange.ACTIVATED
        elif result.decision is DedupDecision.REFRESH and existing is not None:
            existing.mark_observed(
                sequence=trigger.sequence,
                monotonic_ns=trigger.monotonic_ns,
                wall_seconds=trigger.wall_seconds,
                message=trigger.message,
            )
            existing.metadata.update(trigger.metadata)
            lifecycle = existing
            change = WarningChange.DEDUPLICATED

        if lifecycle is not None and change is not None:
            self._notify(
                WarningDelta(
                    warning=lifecycle,
                    change=change,
                    sequence=trigger.sequence,
                    last_sequence=self._last_sequence,
                )
            )

    def _mark_resolved_internal(
        self,
        lifecycle: WarningLifecycle,
        *,
        sequence: int | None,
        monotonic_ns: int,
        wall_seconds: float,
    ) -> None:
        lifecycle.mark_resolved(
            sequence=sequence,
            monotonic_ns=monotonic_ns,
            wall_seconds=wall_seconds,
        )
        self._self_metrics.warnings_resolved += 1
        self._notify(
            WarningDelta(
                warning=lifecycle,
                change=WarningChange.RESOLVED,
                sequence=sequence,
                last_sequence=self._last_sequence,
            )
        )

    def _sweep_expired(
        self,
        *,
        now_monotonic_ns: int,
        now_wall: float,
    ) -> None:
        for lifecycle in list(self._lifecycles.values()):
            if lifecycle.resolved:
                continue
            if self._expiration.is_expired(lifecycle, now_monotonic_ns=now_monotonic_ns):
                lifecycle.mark_expired(
                    monotonic_ns=now_monotonic_ns,
                    wall_seconds=now_wall,
                )
                self._self_metrics.warnings_expired += 1
                self._notify(
                    WarningDelta(
                        warning=lifecycle,
                        change=WarningChange.EXPIRED,
                        sequence=self._last_sequence,
                        last_sequence=self._last_sequence,
                    )
                )

    def _notify(self, delta: WarningDelta) -> None:
        failures = 0
        for sub in self._subscriptions.listeners():
            try:
                sub.listener(delta)
            except Exception as exc:
                failures += 1
                logger.warning(
                    "warning subscriber %d failed for %r/%s: %s",
                    sub.id,
                    delta.warning.warning_id,
                    delta.change.value,
                    exc,
                )
        self._self_metrics.subscription_dispatches += 1
        self._self_metrics.subscription_failures += failures
