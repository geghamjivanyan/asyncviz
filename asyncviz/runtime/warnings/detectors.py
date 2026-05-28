"""Initial detector framework + a handful of canonical detectors.

Each detector implements :class:`WarningDetector`. Thresholds are simple
constants today — a future tuning layer can plumb them through config
without touching the manager.

Detectors fall into two flavors:

* **Event-driven** — react to one :class:`RuntimeEvent` (typically a
  terminal task event). The detector inspects the event and returns
  zero or more :class:`WarningTrigger` candidates.
* **Snapshot-driven** — read aggregate metrics + lineage and decide
  whether a runtime-wide warning should be open.

Both flavors are evaluated through the manager's single dispatch loop so
the wire-side semantics stay uniform.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import TaskCancelledEvent, TaskCompletedEvent
from asyncviz.runtime.events.models.base import GenericEvent
from asyncviz.runtime.events.models.enums import WarningSeverity
from asyncviz.runtime.monitoring.blocking.blocking_events import (
    BLOCKING_ESCALATION_EVENT_TYPE,
    BLOCKING_VIOLATION_EVENT_TYPE,
    BLOCKING_WINDOW_CLOSED_EVENT_TYPE,
)
from asyncviz.runtime.monitoring.event_loop.lag_events import (
    LAG_THRESHOLD_BREACH_EVENT_TYPE,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_events import (
    BLOCKING_WARNING_ACTIVE_EVENT_TYPE,
    BLOCKING_WARNING_ESCALATED_EVENT_TYPE,
    BLOCKING_WARNING_EXPIRED_EVENT_TYPE,
    BLOCKING_WARNING_OPENED_EVENT_TYPE,
    BLOCKING_WARNING_RECOVERED_EVENT_TYPE,
    is_blocking_warning_event,
)
from asyncviz.runtime.warnings.normalization import WarningTrigger

if TYPE_CHECKING:
    from asyncviz.runtime.metrics import RuntimeMetricsAggregator
    from asyncviz.runtime.tasks import TaskRegistry


# ── Thresholds (tunable later) ───────────────────────────────────────────
DEFAULT_SLOW_TASK_SECONDS: float = 5.0
DEFAULT_DEEP_LINEAGE_DEPTH: int = 32
DEFAULT_ACTIVE_TASK_LIMIT: int = 1000
DEFAULT_CANCEL_RATE_PER_SECOND: float = 5.0
DEFAULT_LONG_WAIT_SECONDS: float = 30.0


@dataclass(frozen=True, slots=True)
class DetectorContext:
    """What every detector is allowed to read.

    Held by the manager and passed by reference; detectors MUST NOT
    mutate anything in it.
    """

    registry: TaskRegistry
    aggregator: RuntimeMetricsAggregator | None


@runtime_checkable
class WarningDetector(Protocol):
    """Detector contract.

    ``snapshot_driven=True`` opts the detector into the manager's
    auto-resolution sweep: warnings created by snapshot-driven detectors
    auto-resolve when the next snapshot evaluation doesn't re-fire them.
    Event-driven detectors leave warnings open until explicit resolution
    or expiration.
    """

    name: str
    snapshot_driven: bool

    def evaluate_event(
        self,
        ctx: DetectorContext,
        event: RuntimeEvent,
        *,
        sequence: int | None,
    ) -> Iterable[WarningTrigger]:  # pragma: no cover - protocol
        ...

    def evaluate_snapshot(
        self,
        ctx: DetectorContext,
        *,
        sequence: int | None,
        monotonic_ns: int,
        wall_seconds: float,
    ) -> Iterable[WarningTrigger]:  # pragma: no cover - protocol
        ...


class _BaseDetector:
    """Convenience base — both ``evaluate_*`` methods default to no-op.

    Concrete detectors override only the slot they need. Keeping this an
    optional base (rather than a required parent) preserves the duck-typed
    :class:`WarningDetector` protocol for ad-hoc test detectors.
    """

    name: str = "base"
    snapshot_driven: bool = False

    def evaluate_event(
        self,
        ctx: DetectorContext,
        event: RuntimeEvent,
        *,
        sequence: int | None,
    ) -> Iterable[WarningTrigger]:
        del ctx, event, sequence
        return ()

    def evaluate_snapshot(
        self,
        ctx: DetectorContext,
        *,
        sequence: int | None,
        monotonic_ns: int,
        wall_seconds: float,
    ) -> Iterable[WarningTrigger]:
        del ctx, sequence, monotonic_ns, wall_seconds
        return ()


class SlowTaskDetector(_BaseDetector):
    """Flag any completed task whose duration exceeds ``threshold_seconds``."""

    name = "slow_task"

    def __init__(self, *, threshold_seconds: float = DEFAULT_SLOW_TASK_SECONDS) -> None:
        self.threshold_seconds = threshold_seconds

    def evaluate_event(
        self,
        ctx: DetectorContext,
        event: RuntimeEvent,
        *,
        sequence: int | None,
    ) -> Iterable[WarningTrigger]:
        if not isinstance(event, TaskCompletedEvent):
            return ()
        if event.duration_seconds is None or event.duration_seconds < self.threshold_seconds:
            return ()
        task = ctx.registry.get(event.task_id)
        lineage_root = task.root_task_id if task is not None else None
        return (
            WarningTrigger(
                warning_type=self.name,
                warning_key=f"slow_task:{event.task_id}",
                severity=WarningSeverity.WARNING,
                message=(
                    f"task {event.task_id!r} completed in "
                    f"{event.duration_seconds:.3f}s "
                    f"(threshold {self.threshold_seconds:.3f}s)"
                ),
                detector=self.name,
                sequence=sequence,
                monotonic_ns=event.monotonic_ns,
                wall_seconds=event.timestamp,
                related_task_ids=(event.task_id,),
                lineage_root_id=lineage_root,
                metadata={
                    "duration_seconds": event.duration_seconds,
                    "threshold_seconds": self.threshold_seconds,
                    "coroutine_name": event.coroutine_name,
                },
            ),
        )


class CancellationStormDetector(_BaseDetector):
    """Flag when cancellations/sec exceeds ``threshold_per_second``.

    Snapshot-driven — consults the metrics aggregator's rate meter rather
    than counting events itself.
    """

    name = "cancellation_storm"
    snapshot_driven = True

    def __init__(
        self,
        *,
        threshold_per_second: float = DEFAULT_CANCEL_RATE_PER_SECOND,
    ) -> None:
        self.threshold_per_second = threshold_per_second

    def evaluate_snapshot(
        self,
        ctx: DetectorContext,
        *,
        sequence: int | None,
        monotonic_ns: int,
        wall_seconds: float,
    ) -> Iterable[WarningTrigger]:
        if ctx.aggregator is None:
            return ()
        rate = ctx.aggregator.rate_meter("cancellations").snapshot(
            monotonic_seconds=monotonic_ns / 1_000_000_000
        )
        if rate.rate_per_second < self.threshold_per_second:
            return ()
        return (
            WarningTrigger(
                warning_type=self.name,
                warning_key=f"cancellation_storm:rate_{int(rate.window_seconds)}s",
                severity=WarningSeverity.ERROR,
                message=(
                    f"cancellations at {rate.rate_per_second:.2f}/s "
                    f"(window={rate.window_seconds}s, threshold "
                    f"{self.threshold_per_second:.2f}/s)"
                ),
                detector=self.name,
                # Snapshot-driven detectors emit triggers with ``sequence=None``
                # so repeat evaluation REFRESHES the existing warning (bumps
                # occurrence_count) rather than getting suppressed as stale.
                sequence=None,
                monotonic_ns=monotonic_ns,
                wall_seconds=wall_seconds,
                related_task_ids=(),
                lineage_root_id=None,
                metadata={
                    "rate_per_second": rate.rate_per_second,
                    "threshold_per_second": self.threshold_per_second,
                    "window_seconds": rate.window_seconds,
                },
            ),
        )


class DeepLineageDetector(_BaseDetector):
    """Flag when max observed lineage depth crosses ``threshold``."""

    name = "deep_lineage"
    snapshot_driven = True

    def __init__(self, *, threshold: int = DEFAULT_DEEP_LINEAGE_DEPTH) -> None:
        self.threshold = threshold

    def evaluate_snapshot(
        self,
        ctx: DetectorContext,
        *,
        sequence: int | None,
        monotonic_ns: int,
        wall_seconds: float,
    ) -> Iterable[WarningTrigger]:
        if ctx.aggregator is None:
            return ()
        lineage_metrics = ctx.aggregator.registry.lineage_metrics_snapshot()
        if lineage_metrics.max_depth < self.threshold:
            return ()
        return (
            WarningTrigger(
                warning_type=self.name,
                warning_key=f"deep_lineage:depth_>={self.threshold}",
                severity=WarningSeverity.WARNING,
                message=(
                    f"lineage depth at {lineage_metrics.max_depth} (threshold {self.threshold})"
                ),
                detector=self.name,
                # Snapshot-driven detectors emit triggers with ``sequence=None``
                # so repeat evaluation REFRESHES the existing warning (bumps
                # occurrence_count) rather than getting suppressed as stale.
                sequence=None,
                monotonic_ns=monotonic_ns,
                wall_seconds=wall_seconds,
                related_task_ids=(),
                lineage_root_id=None,
                metadata={
                    "max_depth": lineage_metrics.max_depth,
                    "threshold": self.threshold,
                    "tracked_tasks": lineage_metrics.tracked_tasks,
                },
            ),
        )


class ExcessiveActiveTasksDetector(_BaseDetector):
    """Flag when ``active_tasks`` crosses ``threshold``."""

    name = "excessive_active_tasks"
    snapshot_driven = True

    def __init__(self, *, threshold: int = DEFAULT_ACTIVE_TASK_LIMIT) -> None:
        self.threshold = threshold

    def evaluate_snapshot(
        self,
        ctx: DetectorContext,
        *,
        sequence: int | None,
        monotonic_ns: int,
        wall_seconds: float,
    ) -> Iterable[WarningTrigger]:
        if ctx.aggregator is None:
            return ()
        counts = ctx.aggregator.counts_snapshot()
        active = counts.get("active", 0)
        if active < self.threshold:
            return ()
        return (
            WarningTrigger(
                warning_type=self.name,
                warning_key=f"excessive_active_tasks:>={self.threshold}",
                severity=WarningSeverity.ERROR,
                message=(f"active task count at {active} (threshold {self.threshold})"),
                detector=self.name,
                # Snapshot-driven detectors emit triggers with ``sequence=None``
                # so repeat evaluation REFRESHES the existing warning (bumps
                # occurrence_count) rather than getting suppressed as stale.
                sequence=None,
                monotonic_ns=monotonic_ns,
                wall_seconds=wall_seconds,
                related_task_ids=(),
                lineage_root_id=None,
                metadata={
                    "active": active,
                    "threshold": self.threshold,
                },
            ),
        )


class CancellationOriginDetector(_BaseDetector):
    """Flag any task cancelled with a non-explicit origin (parent / timeout / etc).

    Reserved for the v2 cancellation engine. Today most cancellations are
    ``"explicit"`` / ``"shutdown"`` and silenced; this detector lights up
    once propagation-aware origins start being attributed.
    """

    name = "non_explicit_cancellation"

    def evaluate_event(
        self,
        ctx: DetectorContext,
        event: RuntimeEvent,
        *,
        sequence: int | None,
    ) -> Iterable[WarningTrigger]:
        del ctx
        if not isinstance(event, TaskCancelledEvent):
            return ()
        origin = event.cancellation_origin
        if origin in (None, "explicit", "shutdown"):
            return ()
        return (
            WarningTrigger(
                warning_type=self.name,
                warning_key=f"non_explicit_cancellation:{event.task_id}",
                severity=WarningSeverity.INFO,
                message=(f"task {event.task_id!r} cancelled by {origin!r}"),
                detector=self.name,
                sequence=sequence,
                monotonic_ns=event.monotonic_ns,
                wall_seconds=event.timestamp,
                related_task_ids=(event.task_id,),
                lineage_root_id=None,
                metadata={"cancellation_origin": origin},
            ),
        )


_LAG_SEVERITY_MAP: dict[str, WarningSeverity] = {
    "WARNING": WarningSeverity.WARNING,
    "CRITICAL": WarningSeverity.ERROR,
    "FREEZE": WarningSeverity.CRITICAL,
}


class EventLoopLagDetector(_BaseDetector):
    """Translate ``runtime.monitoring.lag.threshold`` events into warnings.

    Bridges the lag-monitor's threshold-breach stream into the runtime
    warning surface. One warning key per severity tier so an escalating
    incident (warning → critical → freeze) groups under the same lifecycle
    without spamming the dashboard. Refreshes keep the lifecycle current
    while the loop is blocked; resolution lands once breaches stop and
    the warning's TTL expires.
    """

    name = "event_loop_lag"

    def evaluate_event(
        self,
        ctx: DetectorContext,
        event: RuntimeEvent,
        *,
        sequence: int | None,
    ) -> Iterable[WarningTrigger]:
        del ctx
        if not isinstance(event, GenericEvent):
            return ()
        if event.event_type != LAG_THRESHOLD_BREACH_EVENT_TYPE:
            return ()
        payload = event.payload
        severity_name = str(payload.get("severity", "")).upper()
        severity = _LAG_SEVERITY_MAP.get(severity_name)
        if severity is None:
            return ()
        lag_ns = int(payload.get("lag_ns", 0))
        threshold_ns = int(payload.get("threshold_ns", 0))
        measurement = payload.get("measurement") or {}
        sample_index = int(measurement.get("sample_index", -1))
        return (
            WarningTrigger(
                warning_type=self.name,
                warning_key=f"event_loop_lag:{severity_name.lower()}",
                severity=severity,
                message=(
                    f"event loop lag {lag_ns / 1_000_000:.2f}ms "
                    f"crossed {severity_name.lower()} threshold "
                    f"({threshold_ns / 1_000_000:.2f}ms)"
                ),
                detector=self.name,
                sequence=sequence,
                monotonic_ns=event.monotonic_ns,
                wall_seconds=event.timestamp,
                related_task_ids=(),
                lineage_root_id=None,
                metadata={
                    "severity": severity_name,
                    "lag_ns": lag_ns,
                    "lag_ms": lag_ns / 1_000_000,
                    "threshold_ns": threshold_ns,
                    "threshold_ms": threshold_ns / 1_000_000,
                    "sample_index": sample_index,
                },
            ),
        )


_BLOCKING_SEVERITY_MAP: dict[str, WarningSeverity] = {
    "WARNING": WarningSeverity.WARNING,
    "CRITICAL": WarningSeverity.ERROR,
    "FREEZE": WarningSeverity.CRITICAL,
}


class BlockingViolationDetector(_BaseDetector):
    """Translate blocking-detector events into runtime warnings.

    Handles three event types from
    :mod:`asyncviz.runtime.monitoring.blocking`:

    * ``runtime.monitoring.blocking.violation``     — one warning per
      severity tier (refreshes existing lifecycle while the spike
      persists, so cooldown deduplication doesn't double-emit at the
      warning layer either).
    * ``runtime.monitoring.blocking.escalation``    — emits a dedicated
      warning when a window upgrades severity. Same dedup key family as
      violations, just escalation-specific.
    * ``runtime.monitoring.blocking.window.closed`` — emits an
      informational warning summarizing the freeze (duration, peak,
      violation count). Useful for postmortem dashboards.

    Lifecycle: warnings keyed off ``(window_id, severity)`` when a
    window is present so the lifecycle naturally resolves when the
    window closes and TTL expires.
    """

    name = "blocking_violation"

    def evaluate_event(
        self,
        ctx: DetectorContext,
        event: RuntimeEvent,
        *,
        sequence: int | None,
    ) -> Iterable[WarningTrigger]:
        del ctx
        if not isinstance(event, GenericEvent):
            return ()
        if event.event_type == BLOCKING_VIOLATION_EVENT_TYPE:
            return self._trigger_for_violation(event, sequence)
        if event.event_type == BLOCKING_ESCALATION_EVENT_TYPE:
            return self._trigger_for_escalation(event, sequence)
        if event.event_type == BLOCKING_WINDOW_CLOSED_EVENT_TYPE:
            return self._trigger_for_window_closed(event, sequence)
        return ()

    def _trigger_for_violation(
        self, event: GenericEvent, sequence: int | None
    ) -> Iterable[WarningTrigger]:
        payload = event.payload
        severity_name = str(payload.get("effective_severity", "")).upper()
        severity = _BLOCKING_SEVERITY_MAP.get(severity_name)
        if severity is None:
            return ()
        classification = payload.get("classification") or {}
        lag_ns = int(classification.get("lag_ns", 0))
        threshold_ns = int(classification.get("threshold_ns", 0))
        active_window = payload.get("active_window") or {}
        window_id = str(active_window.get("window_id", ""))
        # Key off (window_id, severity) when a window is active so the
        # lifecycle correlates with the freeze. Fall back to severity-only
        # for severity tiers below the window-open threshold.
        if window_id:
            key = f"blocking_violation:{window_id}:{severity_name.lower()}"
        else:
            key = f"blocking_violation:{severity_name.lower()}"
        return (
            WarningTrigger(
                warning_type=self.name,
                warning_key=key,
                severity=severity,
                message=(
                    f"event loop blocking violation: "
                    f"{lag_ns / 1_000_000:.2f}ms "
                    f"({severity_name.lower()} threshold "
                    f"{threshold_ns / 1_000_000:.2f}ms)"
                ),
                detector=self.name,
                sequence=sequence,
                monotonic_ns=event.monotonic_ns,
                wall_seconds=event.timestamp,
                related_task_ids=(),
                lineage_root_id=None,
                metadata={
                    "kind": "violation",
                    "severity": severity_name,
                    "lag_ns": lag_ns,
                    "lag_ms": lag_ns / 1_000_000,
                    "threshold_ns": threshold_ns,
                    "window_id": window_id or None,
                    "consecutive_warning": payload.get("consecutive_warning"),
                    "consecutive_critical": payload.get("consecutive_critical"),
                    "consecutive_freeze": payload.get("consecutive_freeze"),
                },
            ),
        )

    def _trigger_for_escalation(
        self, event: GenericEvent, sequence: int | None
    ) -> Iterable[WarningTrigger]:
        payload = event.payload
        to_name = str(payload.get("to_severity", "")).upper()
        severity = _BLOCKING_SEVERITY_MAP.get(to_name)
        if severity is None:
            return ()
        from_name = str(payload.get("from_severity", "")).upper()
        active_window = payload.get("active_window") or {}
        window_id = str(active_window.get("window_id", ""))
        if window_id:
            key = f"blocking_escalation:{window_id}:{to_name.lower()}"
        else:
            key = f"blocking_escalation:{to_name.lower()}"
        return (
            WarningTrigger(
                warning_type=f"{self.name}:escalation",
                warning_key=key,
                severity=severity,
                message=(f"blocking severity escalated {from_name.lower()} -> {to_name.lower()}"),
                detector=self.name,
                sequence=sequence,
                monotonic_ns=event.monotonic_ns,
                wall_seconds=event.timestamp,
                related_task_ids=(),
                lineage_root_id=None,
                metadata={
                    "kind": "escalation",
                    "from_severity": from_name,
                    "to_severity": to_name,
                    "window_id": window_id or None,
                },
            ),
        )

    def _trigger_for_window_closed(
        self, event: GenericEvent, sequence: int | None
    ) -> Iterable[WarningTrigger]:
        payload = event.payload
        window = payload.get("window") or {}
        peak_name = str(window.get("peak_severity", "")).upper()
        # Closed-window summaries always surface at WARNING — the freeze
        # is over; CRITICAL/FREEZE warnings during the window already
        # paged.
        severity = WarningSeverity.WARNING
        window_id = str(window.get("window_id", ""))
        duration_ns = int(window.get("duration_ns", 0))
        violation_count = int(window.get("violation_count", 0))
        peak_lag_ns = int(window.get("peak_lag_ns", 0))
        return (
            WarningTrigger(
                warning_type=f"{self.name}:window_closed",
                warning_key=f"blocking_window_closed:{window_id}",
                severity=severity,
                message=(
                    f"blocking window {window_id} closed: "
                    f"{duration_ns / 1_000_000:.2f}ms, "
                    f"{violation_count} violations, "
                    f"peak {peak_lag_ns / 1_000_000:.2f}ms ({peak_name.lower()})"
                ),
                detector=self.name,
                sequence=sequence,
                monotonic_ns=event.monotonic_ns,
                wall_seconds=event.timestamp,
                related_task_ids=(),
                lineage_root_id=None,
                metadata={
                    "kind": "window_closed",
                    "window_id": window_id,
                    "duration_ns": duration_ns,
                    "duration_ms": duration_ns / 1_000_000,
                    "violation_count": violation_count,
                    "peak_lag_ns": peak_lag_ns,
                    "peak_severity": peak_name,
                },
            ),
        )


_BLOCKING_WARNING_SEVERITY_MAP: dict[str, WarningSeverity] = {
    "WARNING": WarningSeverity.WARNING,
    "CRITICAL": WarningSeverity.ERROR,
    "FREEZE": WarningSeverity.CRITICAL,
}


class BlockingWarningGroupDetector(_BaseDetector):
    """Drive the warning manager from the canonical blocking-warning events.

    Subscribes to the five transition event types published by
    :class:`asyncviz.runtime.warnings.blocking.BlockingWarningEmitter`
    and translates them into one :class:`WarningTrigger` per
    ``group_id``:

    * ``opened``     → activate (severity from the payload).
    * ``escalated``  → refresh + bump severity.
    * ``active``     → refresh (rate-limited by the emitter's dedup).
    * ``recovered``  → refresh once with the final severity; the
      warning manager's TTL sweep then expires the lifecycle.
    * ``expired``    → refresh with the same severity; the recovered
      state stays in history.

    Keyed by ``group_id`` so the warning manager naturally maps one
    freeze incident to one lifecycle. The Task-6.2
    :class:`BlockingViolationDetector` remains available for users who
    want raw per-event warnings; the dashboard's default lineup uses
    this one because the group-level view is more operator-friendly.
    """

    name = "blocking_warning_group"

    def evaluate_event(
        self,
        ctx: DetectorContext,
        event: RuntimeEvent,
        *,
        sequence: int | None,
    ) -> Iterable[WarningTrigger]:
        del ctx
        if not isinstance(event, GenericEvent):
            return ()
        if not is_blocking_warning_event(event.event_type):
            return ()
        payload = event.payload
        group_id = str(payload.get("group_id", ""))
        if not group_id:
            return ()
        severity_name = str(payload.get("severity", "")).upper()
        severity = _BLOCKING_WARNING_SEVERITY_MAP.get(severity_name, WarningSeverity.WARNING)
        transition = str(payload.get("transition", "")).lower() or event.event_type
        message = self._compose_message(payload, transition)
        return (
            WarningTrigger(
                warning_type=self.name,
                warning_key=f"blocking_warning_group:{group_id}",
                severity=severity,
                message=message,
                detector=self.name,
                sequence=sequence,
                monotonic_ns=event.monotonic_ns,
                wall_seconds=event.timestamp,
                related_task_ids=self._related_task_ids(payload),
                lineage_root_id=None,
                metadata=self._build_metadata(payload, transition),
            ),
        )

    @staticmethod
    def _related_task_ids(payload: dict[str, object]) -> tuple[str, ...]:
        task_id = payload.get("task_id")
        return (str(task_id),) if isinstance(task_id, str) and task_id else ()

    @staticmethod
    def _build_metadata(payload: dict[str, object], transition: str) -> dict[str, object]:
        peak_lag_ns = int(payload.get("peak_lag_ns", 0))
        duration_ns = int(payload.get("freeze_duration_ns", 0))
        return {
            "kind": "blocking_warning_group",
            "transition": transition,
            "window_id": payload.get("window_id"),
            "warning_id": payload.get("warning_id"),
            "group_id": payload.get("group_id"),
            "severity": payload.get("severity"),
            "peak_severity": payload.get("peak_severity"),
            "peak_lag_ns": peak_lag_ns,
            "peak_lag_ms": peak_lag_ns / 1_000_000,
            "freeze_duration_ns": duration_ns,
            "freeze_duration_ms": duration_ns / 1_000_000,
            "violation_count": payload.get("violation_count"),
            "escalation_count": payload.get("escalation_count"),
            "capture_ids": payload.get("capture_ids") or [],
            "task_name": payload.get("task_name"),
            "coroutine_name": payload.get("coroutine_name"),
            "state": payload.get("state"),
            "first_seen_ns": payload.get("first_seen_ns"),
            "last_seen_ns": payload.get("last_seen_ns"),
        }

    @staticmethod
    def _compose_message(payload: dict[str, object], transition: str) -> str:
        sev = str(payload.get("severity", "")).lower() or "unknown"
        peak_lag_ms = int(payload.get("peak_lag_ns", 0)) / 1_000_000
        duration_ms = int(payload.get("freeze_duration_ns", 0)) / 1_000_000
        window_id = payload.get("window_id")
        if transition == "opened":
            base = f"event loop blocking ({sev}) opened"
        elif transition == "escalated":
            base = f"event loop blocking escalated to {sev}"
        elif transition == "recovered":
            base = f"event loop blocking ({sev}) recovered after {duration_ms:.1f}ms"
        elif transition == "expired":
            base = f"event loop blocking ({sev}) expired after {duration_ms:.1f}ms"
        else:
            base = f"event loop blocking ({sev}) refresh"
        if window_id:
            base += f" [window={window_id}]"
        if peak_lag_ms:
            base += f" peak={peak_lag_ms:.1f}ms"
        return base


# Acknowledged event type constants — surfaces the detector handles.
BLOCKING_WARNING_GROUP_EVENT_TYPES: tuple[str, ...] = (
    BLOCKING_WARNING_OPENED_EVENT_TYPE,
    BLOCKING_WARNING_ESCALATED_EVENT_TYPE,
    BLOCKING_WARNING_ACTIVE_EVENT_TYPE,
    BLOCKING_WARNING_RECOVERED_EVENT_TYPE,
    BLOCKING_WARNING_EXPIRED_EVENT_TYPE,
)


def default_detectors() -> list[WarningDetector]:
    """The detector set the dashboard wires up by default.

    Two blocking-related entries:

    * :class:`BlockingViolationDetector` — fine-grained, one warning
      per raw blocking event (Task 6.2 wire path).
    * :class:`BlockingWarningGroupDetector` — coarse grouped warning
      per freeze window (Task 6.4 emitter path). Operator-focused
      view; keyed by ``group_id`` so escalations refresh the same
      lifecycle.

    They use distinct warning-key namespaces so they coexist without
    duplicating user-visible warnings — the dashboard can choose to
    render one, the other, or both depending on operator preference.
    """
    return [
        SlowTaskDetector(),
        CancellationStormDetector(),
        DeepLineageDetector(),
        ExcessiveActiveTasksDetector(),
        CancellationOriginDetector(),
        EventLoopLagDetector(),
        BlockingViolationDetector(),
        BlockingWarningGroupDetector(),
    ]
