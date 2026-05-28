from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HistogramModel(BaseModel):
    """Wire shape for :class:`HistogramSnapshot`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int
    min_value: float
    max_value: float
    mean: float
    p50: float
    p95: float
    p99: float
    sum_value: float
    samples: int


class DurationStatsModel(BaseModel):
    """Wire shape for one duration bucket (e.g. ``completed``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    count: int
    total_seconds: float
    min_seconds: float
    max_seconds: float
    mean_seconds: float
    histogram: HistogramModel


class TaskCountsModel(BaseModel):
    """Per-state task tally."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int
    active: int
    waiting: int
    completed: int
    cancelled: int
    failed: int
    terminal: int


class ThroughputModel(BaseModel):
    """Rolling-window event-rate view."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tasks_per_second: float
    completions_per_second: float
    cancellations_per_second: float
    failures_per_second: float
    window_seconds: int


class DurationsByStateModel(BaseModel):
    """Duration stats bucketed by terminal state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    completed: DurationStatsModel
    cancelled: DurationStatsModel
    failed: DurationStatsModel
    overall: DurationStatsModel


class CoroutineRowModel(BaseModel):
    """Per-coroutine roll-up row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    coroutine_name: str
    task_count: int
    active_count: int
    completed_count: int
    cancelled_count: int
    failed_count: int
    completed_total_duration_seconds: float
    completed_avg_duration_seconds: float | None
    max_duration_seconds: float | None


class LineageMetricsModel(BaseModel):
    """Hierarchy roll-up."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    root_count: int
    max_depth: int
    average_fanout: float
    largest_tree_size: int
    largest_tree_root_id: str | None
    cancellations_propagated: int


class TopTaskModel(BaseModel):
    """One row in a top-N task listing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    coroutine_name: str | None
    task_name: str | None
    duration_seconds: float
    state: str


class TimelineSummaryModel(BaseModel):
    """Subset of :class:`TimelineSnapshot` rolled into the aggregate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    transitions_applied: int
    transitions_rejected: int
    segments_opened: int
    segments_closed: int
    segments_by_type: dict[str, int]
    invalid_transitions: int
    active_segments: int
    finalized_spans: int


class AggregatorSelfMetricsModel(BaseModel):
    """The aggregator's view of itself — for observability of observability."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    events_observed: int
    events_stale: int
    events_duplicate: int
    snapshots_emitted: int
    rebuilds_completed: int
    subscription_dispatches: int
    subscription_failures: int
    last_event_sequence: int


class RuntimeMetricsAggregateSnapshot(BaseModel):
    """Authoritative aggregate snapshot.

    Mirror this exactly in TypeScript ``RuntimeMetricsAggregateSnapshot``.
    All nested models use ``extra='forbid'`` so drift on either side
    surfaces in CI immediately.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    generated_at: float
    generated_at_monotonic_ns: int
    runtime_id: str
    last_sequence: int
    runtime_uptime_seconds: float

    counts: TaskCountsModel
    throughput: ThroughputModel
    durations: DurationsByStateModel
    coroutines: list[CoroutineRowModel] = Field(default_factory=list)
    lineage: LineageMetricsModel
    cancellations_by_origin: dict[str, int] = Field(default_factory=dict)
    longest_tasks: list[TopTaskModel] = Field(default_factory=list)
    shortest_tasks: list[TopTaskModel] = Field(default_factory=list)
    timeline: TimelineSummaryModel | None = None
    self_metrics: AggregatorSelfMetricsModel
