"""Per-intent helpers — small mutations on the aggregator's working set.

Reducers update only counter-style state; the snapshot builder composes
everything else from registries / timeline / lineage at read time.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.metrics.counters import CounterSet
from asyncviz.runtime.metrics.durations import DurationAggregator
from asyncviz.runtime.metrics.normalization import MetricsIntent, NormalizedMetricsEvent


@dataclass(frozen=True, slots=True)
class ReducerOutcome:
    """The delta map a reducer produced. Consumed by streaming subscribers."""

    changes: dict[str, int]
    duration_added_seconds: float | None
    terminal_state: str | None


def apply_lifecycle(
    norm: NormalizedMetricsEvent,
    *,
    counts: CounterSet,
    cancellations_by_origin: CounterSet,
    coroutine_counts: CounterSet,
    completed_durations: DurationAggregator,
    cancelled_durations: DurationAggregator,
    failed_durations: DurationAggregator,
    overall_durations: DurationAggregator,
) -> ReducerOutcome:
    """Update lifecycle counters + duration aggregators for one event."""
    changes: dict[str, int] = {}
    duration_added: float | None = None
    terminal_state: str | None = None
    coroutine_key = norm.coroutine_name or "<anonymous>"

    match norm.intent:
        case MetricsIntent.CREATE:
            counts.inc("total")
            counts.inc("active")
            coroutine_counts.inc(coroutine_key)
            changes = {"total": 1, "active": 1}
        case MetricsIntent.WAIT:
            counts.inc("waiting")
            counts.inc("active", delta=-0)  # no net change to active
            changes = {"waiting": 1}
        case MetricsIntent.START | MetricsIntent.RESUME:
            # Transitions within active states — no count change.
            changes = {}
        case MetricsIntent.COMPLETE:
            counts.inc("active", delta=-1)
            counts.inc("completed")
            counts.inc("terminal")
            changes = {"active": -1, "completed": 1, "terminal": 1}
            terminal_state = "completed"
            if norm.duration_seconds is not None:
                completed_durations.observe(norm.duration_seconds)
                overall_durations.observe(norm.duration_seconds)
                duration_added = norm.duration_seconds
        case MetricsIntent.CANCEL:
            counts.inc("active", delta=-1)
            counts.inc("cancelled")
            counts.inc("terminal")
            origin_key = norm.cancellation_origin or "unknown"
            cancellations_by_origin.inc(origin_key)
            changes = {"active": -1, "cancelled": 1, "terminal": 1}
            terminal_state = "cancelled"
            if norm.duration_seconds is not None:
                cancelled_durations.observe(norm.duration_seconds)
                overall_durations.observe(norm.duration_seconds)
                duration_added = norm.duration_seconds
        case MetricsIntent.FAIL:
            counts.inc("active", delta=-1)
            counts.inc("failed")
            counts.inc("terminal")
            changes = {"active": -1, "failed": 1, "terminal": 1}
            terminal_state = "failed"
            if norm.duration_seconds is not None:
                failed_durations.observe(norm.duration_seconds)
                overall_durations.observe(norm.duration_seconds)
                duration_added = norm.duration_seconds
        case MetricsIntent.IGNORE:
            changes = {}

    return ReducerOutcome(
        changes=changes,
        duration_added_seconds=duration_added,
        terminal_state=terminal_state,
    )
