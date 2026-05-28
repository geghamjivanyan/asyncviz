"""Read-only convenience API on top of the aggregator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from asyncviz.runtime.metrics.durations import DurationStatsSnapshot
from asyncviz.runtime.metrics.lineage import (
    LineageAggregateSnapshot,
    aggregate_lineage,
)
from asyncviz.runtime.metrics.projections import (
    CoroutineMetricsRow,
    aggregate_coroutine_groups,
)
from asyncviz.runtime.tasks import TaskRegistry

if TYPE_CHECKING:
    from asyncviz.runtime.metrics.aggregator import RuntimeMetricsAggregator


class MetricsQueryService:
    """Convenience reads over a live :class:`RuntimeMetricsAggregator`."""

    __slots__ = ("_aggregator", "_registry")

    def __init__(self, aggregator: RuntimeMetricsAggregator, registry: TaskRegistry) -> None:
        self._aggregator = aggregator
        self._registry = registry

    def get_task_counts(self) -> dict[str, int]:
        return self._aggregator.counts_snapshot()

    def get_cancellations_by_origin(self) -> dict[str, int]:
        return self._aggregator.cancellations_by_origin.snapshot()

    def get_coroutine_metrics(self) -> list[CoroutineMetricsRow]:
        return aggregate_coroutine_groups(self._registry.snapshot_all_tasks())

    def get_lineage_metrics(self) -> LineageAggregateSnapshot:
        return aggregate_lineage(self._registry.snapshot_all_tasks())

    def get_duration_summary(self) -> dict[str, DurationStatsSnapshot]:
        return {
            "completed": self._aggregator.completed_durations.snapshot(),
            "cancelled": self._aggregator.cancelled_durations.snapshot(),
            "failed": self._aggregator.failed_durations.snapshot(),
            "overall": self._aggregator.overall_durations.snapshot(),
        }
