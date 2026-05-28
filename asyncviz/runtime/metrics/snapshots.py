"""Compose the aggregate snapshot from the aggregator's working state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from asyncviz.runtime.clock import RuntimeClock
from asyncviz.runtime.metrics.durations import DurationStatsSnapshot
from asyncviz.runtime.metrics.histograms import HistogramSnapshot
from asyncviz.runtime.metrics.lineage import aggregate_lineage
from asyncviz.runtime.metrics.models import (
    AggregatorSelfMetricsModel,
    CoroutineRowModel,
    DurationsByStateModel,
    DurationStatsModel,
    HistogramModel,
    LineageMetricsModel,
    RuntimeMetricsAggregateSnapshot,
    TaskCountsModel,
    ThroughputModel,
    TimelineSummaryModel,
    TopTaskModel,
)
from asyncviz.runtime.metrics.projections import (
    aggregate_coroutine_groups,
    longest_running_tasks,
    shortest_running_tasks,
)
from asyncviz.runtime.tasks import TaskRegistry

if TYPE_CHECKING:
    from asyncviz.runtime.metrics.aggregator import RuntimeMetricsAggregator
    from asyncviz.runtime.timeline import TimelineSegmentEngine


def _histogram_to_model(hs: HistogramSnapshot) -> HistogramModel:
    return HistogramModel(
        count=hs.count,
        min_value=hs.min_value,
        max_value=hs.max_value,
        mean=hs.mean,
        p50=hs.p50,
        p95=hs.p95,
        p99=hs.p99,
        sum_value=hs.sum_value,
        samples=hs.samples,
    )


def _duration_to_model(ds: DurationStatsSnapshot) -> DurationStatsModel:
    return DurationStatsModel(
        count=ds.count,
        total_seconds=ds.total_seconds,
        min_seconds=ds.min_seconds if ds.count else 0.0,
        max_seconds=ds.max_seconds if ds.count else 0.0,
        mean_seconds=ds.mean_seconds,
        histogram=_histogram_to_model(ds.histogram),
    )


def build_aggregate_snapshot(
    aggregator: RuntimeMetricsAggregator,
    registry: TaskRegistry,
    clock: RuntimeClock,
    *,
    timeline_engine: TimelineSegmentEngine | None = None,
    longest_limit: int = 10,
    shortest_limit: int = 10,
) -> RuntimeMetricsAggregateSnapshot:
    """Compose the canonical aggregate snapshot."""
    tasks = list(registry.snapshot_all_tasks())

    counts_snapshot = aggregator.counts_snapshot()
    counts_model = TaskCountsModel(
        total=counts_snapshot.get("total", 0),
        active=counts_snapshot.get("active", 0),
        waiting=counts_snapshot.get("waiting", 0),
        completed=counts_snapshot.get("completed", 0),
        cancelled=counts_snapshot.get("cancelled", 0),
        failed=counts_snapshot.get("failed", 0),
        terminal=counts_snapshot.get("terminal", 0),
    )

    monotonic_seconds = clock.runtime_uptime()
    tasks_rate = aggregator.rate_meter("tasks").snapshot(monotonic_seconds=monotonic_seconds)
    completions_rate = aggregator.rate_meter("completions").snapshot(
        monotonic_seconds=monotonic_seconds
    )
    cancellations_rate = aggregator.rate_meter("cancellations").snapshot(
        monotonic_seconds=monotonic_seconds
    )
    failures_rate = aggregator.rate_meter("failures").snapshot(monotonic_seconds=monotonic_seconds)
    throughput = ThroughputModel(
        tasks_per_second=tasks_rate.rate_per_second,
        completions_per_second=completions_rate.rate_per_second,
        cancellations_per_second=cancellations_rate.rate_per_second,
        failures_per_second=failures_rate.rate_per_second,
        window_seconds=tasks_rate.window_seconds,
    )

    durations = DurationsByStateModel(
        completed=_duration_to_model(aggregator.completed_durations.snapshot()),
        cancelled=_duration_to_model(aggregator.cancelled_durations.snapshot()),
        failed=_duration_to_model(aggregator.failed_durations.snapshot()),
        overall=_duration_to_model(aggregator.overall_durations.snapshot()),
    )

    coroutine_rows = aggregate_coroutine_groups(tasks)
    coroutines = [
        CoroutineRowModel(
            coroutine_name=row.coroutine_name,
            task_count=row.task_count,
            active_count=row.active_count,
            completed_count=row.completed_count,
            cancelled_count=row.cancelled_count,
            failed_count=row.failed_count,
            completed_total_duration_seconds=row.completed_total_duration_seconds,
            completed_avg_duration_seconds=row.completed_avg_duration_seconds,
            max_duration_seconds=row.max_duration_seconds,
        )
        for row in coroutine_rows
    ]

    lineage_aggregate = aggregate_lineage(tasks)
    lineage_model = LineageMetricsModel(
        root_count=lineage_aggregate.root_count,
        max_depth=lineage_aggregate.max_depth,
        average_fanout=lineage_aggregate.average_fanout,
        largest_tree_size=lineage_aggregate.largest_tree_size,
        largest_tree_root_id=lineage_aggregate.largest_tree_root_id,
        cancellations_propagated=lineage_aggregate.cancellations_propagated,
    )

    longest = [
        TopTaskModel(
            task_id=t.task_id,
            coroutine_name=t.coroutine_name,
            task_name=t.task_name,
            duration_seconds=t.duration_seconds or 0.0,
            state=t.state.value,
        )
        for t in longest_running_tasks(tasks, limit=longest_limit)
    ]
    shortest = [
        TopTaskModel(
            task_id=t.task_id,
            coroutine_name=t.coroutine_name,
            task_name=t.task_name,
            duration_seconds=t.duration_seconds or 0.0,
            state=t.state.value,
        )
        for t in shortest_running_tasks(tasks, limit=shortest_limit)
    ]

    timeline_model: TimelineSummaryModel | None = None
    if timeline_engine is not None:
        tm = timeline_engine.metrics_snapshot()
        timeline_model = TimelineSummaryModel(
            transitions_applied=tm.transitions_applied,
            transitions_rejected=tm.transitions_rejected,
            segments_opened=tm.segments_opened,
            segments_closed=tm.segments_closed,
            segments_by_type=dict(tm.segments_by_type),
            invalid_transitions=tm.invalid_transitions,
            active_segments=tm.active_segments,
            finalized_spans=tm.finalized_spans,
        )

    self_metrics_snap = aggregator.self_metrics_snapshot()
    self_metrics = AggregatorSelfMetricsModel(
        events_observed=self_metrics_snap.events_observed,
        events_stale=self_metrics_snap.events_stale,
        events_duplicate=self_metrics_snap.events_duplicate,
        snapshots_emitted=self_metrics_snap.snapshots_emitted,
        rebuilds_completed=self_metrics_snap.rebuilds_completed,
        subscription_dispatches=self_metrics_snap.subscription_dispatches,
        subscription_failures=self_metrics_snap.subscription_failures,
        last_event_sequence=self_metrics_snap.last_event_sequence,
    )

    return RuntimeMetricsAggregateSnapshot(
        generated_at=clock.now(),
        generated_at_monotonic_ns=clock.monotonic_ns(),
        runtime_id=str(clock.runtime_id),
        last_sequence=aggregator.last_sequence,
        runtime_uptime_seconds=clock.runtime_uptime(),
        counts=counts_model,
        throughput=throughput,
        durations=durations,
        coroutines=coroutines,
        lineage=lineage_model,
        cancellations_by_origin=aggregator.cancellations_by_origin.snapshot(),
        longest_tasks=longest,
        shortest_tasks=shortest,
        timeline=timeline_model,
        self_metrics=self_metrics,
    )
