"""Canonical runtime metrics aggregator.

Public surface:

* :class:`RuntimeMetricsAggregator` — the analytics service. Subscribes to
  :class:`RuntimeStateStore` and incrementally maintains lifecycle counters,
  duration histograms, rate meters, and cancellation-origin buckets.
* :class:`RuntimeMetricsAggregateSnapshot` — Pydantic wire model. Mirror
  this in the TypeScript ``RuntimeMetricsAggregateSnapshot`` interface.
* :class:`MetricsDelta` / :class:`MetricsSubscription` — streaming types.
* :class:`MetricsQueryService` — read-only convenience over the aggregator.
* Primitives: :class:`CounterSet`, :class:`ApproxHistogram`,
  :class:`RateMeter`, :class:`DurationAggregator`. Composable; reusable in
  future analytics layers.
* exceptions — :class:`MetricsError`, :class:`MetricsRebuildError`,
  :class:`MetricsSubscriptionError`.

Design rule: a runtime has exactly **one** :class:`RuntimeMetricsAggregator`.
It composes the :class:`TaskRegistry` (for lineage / coroutine rollups) and
optionally the :class:`TimelineSegmentEngine` (for segment-level summaries)
— it does not duplicate their indexes.
"""

from asyncviz.runtime.metrics.aggregator import (
    AggregatorSelfMetricsSnapshot,
    RuntimeMetricsAggregator,
)
from asyncviz.runtime.metrics.counters import CounterSet
from asyncviz.runtime.metrics.durations import (
    DurationAggregator,
    DurationStatsSnapshot,
)
from asyncviz.runtime.metrics.exceptions import (
    MetricsError,
    MetricsRebuildError,
    MetricsSubscriptionError,
)
from asyncviz.runtime.metrics.histograms import (
    DEFAULT_RESERVOIR_CAPACITY,
    ApproxHistogram,
    HistogramSnapshot,
)
from asyncviz.runtime.metrics.lineage import (
    LineageAggregateSnapshot,
    aggregate_lineage,
)
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
from asyncviz.runtime.metrics.normalization import (
    MetricsIntent,
    NormalizedMetricsEvent,
    is_terminal_intent,
    normalize,
)
from asyncviz.runtime.metrics.projections import (
    CoroutineMetricsRow,
    aggregate_coroutine_groups,
    longest_running_tasks,
    shortest_running_tasks,
)
from asyncviz.runtime.metrics.queries import MetricsQueryService
from asyncviz.runtime.metrics.rates import RateMeter, RateSnapshot
from asyncviz.runtime.metrics.reducers import ReducerOutcome, apply_lifecycle
from asyncviz.runtime.metrics.snapshots import build_aggregate_snapshot
from asyncviz.runtime.metrics.streaming import (
    MetricsDelta,
    MetricsListener,
    MetricsSubscription,
    MetricsSubscriptionRegistry,
)

__all__ = [
    "DEFAULT_RESERVOIR_CAPACITY",
    "AggregatorSelfMetricsModel",
    "AggregatorSelfMetricsSnapshot",
    "ApproxHistogram",
    "CoroutineMetricsRow",
    "CoroutineRowModel",
    "CounterSet",
    "DurationAggregator",
    "DurationStatsModel",
    "DurationStatsSnapshot",
    "DurationsByStateModel",
    "HistogramModel",
    "HistogramSnapshot",
    "LineageAggregateSnapshot",
    "LineageMetricsModel",
    "MetricsDelta",
    "MetricsError",
    "MetricsIntent",
    "MetricsListener",
    "MetricsQueryService",
    "MetricsRebuildError",
    "MetricsSubscription",
    "MetricsSubscriptionError",
    "MetricsSubscriptionRegistry",
    "NormalizedMetricsEvent",
    "RateMeter",
    "RateSnapshot",
    "ReducerOutcome",
    "RuntimeMetricsAggregateSnapshot",
    "RuntimeMetricsAggregator",
    "TaskCountsModel",
    "ThroughputModel",
    "TimelineSummaryModel",
    "TopTaskModel",
    "aggregate_coroutine_groups",
    "aggregate_lineage",
    "apply_lifecycle",
    "build_aggregate_snapshot",
    "is_terminal_intent",
    "longest_running_tasks",
    "normalize",
    "shortest_running_tasks",
]
