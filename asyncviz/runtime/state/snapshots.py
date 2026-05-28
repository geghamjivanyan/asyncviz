"""Snapshot builder — composes registry + lineage + projections into one wire artifact."""

from __future__ import annotations

from asyncviz.runtime.clock import RuntimeClock
from asyncviz.runtime.lineage import LineageTracker
from asyncviz.runtime.state.indexes import build_index_view
from asyncviz.runtime.state.models import (
    RuntimeLineageSummary,
    RuntimeStateMetrics,
    RuntimeStateSnapshot,
)
from asyncviz.runtime.state.projections import (
    cancellations_by_origin_projection,
    coroutine_groups_projection,
    lineage_tree_projection,
)
from asyncviz.runtime.state.reducers import TransitionHistory
from asyncviz.runtime.tasks import TaskRegistry


def build_runtime_snapshot(
    registry: TaskRegistry,
    lineage: LineageTracker,
    clock: RuntimeClock,
    *,
    last_sequence: int,
    last_event_id: str | None,
    include_projections: bool = True,
    history: TransitionHistory | None = None,
    include_transitions: bool = False,
) -> RuntimeStateSnapshot:
    """Materialize a :class:`RuntimeStateSnapshot` from the live store state.

    Pulls in *all* tasks (not just active), every metric the registry tracks,
    the lineage summary, and (by default) the default projections. Callers
    that need a small payload — e.g. the heartbeat path — can set
    ``include_projections=False``.
    """
    tasks = list(registry.snapshot_all_tasks())
    task_index = build_index_view(registry)
    registry_metrics = registry.metrics_snapshot()
    lineage_metrics = lineage.metrics_snapshot()

    summary_metrics = RuntimeStateMetrics(
        total_tasks=registry_metrics.total_tasks,
        active_tasks=registry_metrics.active_tasks,
        completed_tasks=registry_metrics.completed_tasks,
        cancelled_tasks=registry_metrics.cancelled_tasks,
        failed_tasks=registry_metrics.failed_tasks,
        terminal_tasks=registry_metrics.terminal_tasks,
        average_duration_seconds=registry_metrics.average_duration_seconds,
        cancellations_by_origin=dict(registry_metrics.cancellations_by_origin),
        rejected_transitions=registry_metrics.rejected_transitions,
    )

    summary_lineage = RuntimeLineageSummary(
        tracked_tasks=lineage_metrics.tracked_tasks,
        root_tasks=lineage_metrics.root_tasks,
        max_depth=lineage_metrics.max_depth,
        orphan_links=lineage_metrics.orphan_links,
        cyclic_rejections=lineage_metrics.cyclic_rejections,
        roots=list(lineage.list_roots()),
    )

    projections: dict[str, object] = {}
    if include_projections:
        projections["lineage_tree"] = lineage_tree_projection(tasks, lineage=lineage)
        projections["coroutine_groups"] = coroutine_groups_projection(tasks)
        projections["cancellations_by_origin"] = cancellations_by_origin_projection(registry)

    transitions: dict[str, list[dict[str, object]]] = {}
    if include_transitions and history is not None:
        # Only export histories for tasks the registry currently knows
        # about — keeps stale entries from leaking after ``rebuild`` or
        # snapshot pruning eventually lands.
        known_ids = {snap.task_id for snap in tasks}
        for task_id, records in history.export().items():
            if task_id in known_ids:
                transitions[task_id] = records

    return RuntimeStateSnapshot(
        generated_at=clock.now(),
        generated_at_monotonic_ns=clock.monotonic_ns(),
        last_sequence=last_sequence,
        last_event_id=last_event_id,
        runtime_id=str(clock.runtime_id),
        tasks=tasks,
        task_ids_by_state=task_index.by_state,
        metrics=summary_metrics,
        lineage=summary_lineage,
        projections=projections,
        transitions=transitions,
    )
