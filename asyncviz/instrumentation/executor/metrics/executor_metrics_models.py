"""Typed snapshot + delta models for the executor metrics engine.

Mirrors the queue-metrics models — frozen dataclasses with JSON-safe
``to_dict``. Snapshots are the wire shape returned by the diagnostics
endpoint and the in-memory shape held by per-executor state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

#: Saturation bands — single source of truth. Engine + events + diagnostics
#: all use these exact strings.
SaturationLevel = Literal["calm", "warning", "critical"]


@dataclass(frozen=True, slots=True)
class ExecutorUtilizationSnapshot:
    active_workers: int = 0
    """Work items currently in-flight on this executor."""

    peak_active_workers: int = 0
    """Highest active-worker count observed in the session."""

    max_workers: int | None = None
    """The executor's configured worker cap. ``None`` for executors
    that don't expose ``_max_workers``."""

    utilization_ratio: float = 0.0
    """``active_workers / max_workers`` clamped to ``[0, 1]``;
    ``0`` when ``max_workers`` is None or zero."""

    mean_utilization: float = 0.0
    """Mean of recent active-worker samples / max_workers."""

    sample_count: int = 0


@dataclass(frozen=True, slots=True)
class ExecutorThroughputSnapshot:
    submissions: int = 0
    completions: int = 0
    failures: int = 0
    cancellations: int = 0
    submission_rate: float = 0.0
    completion_rate: float = 0.0
    backlog: int = 0
    """``submissions - completions - failures - cancellations``;
    the count of work items that have been submitted but not yet
    finished. Includes still-queued items + in-flight ones."""


@dataclass(frozen=True, slots=True)
class ExecutorLatencySnapshot:
    """Bounded approximation of submission / execution latency
    distribution.

    Mean is exact (running average). Percentiles are reservoir-sampled.
    """

    count: int = 0
    mean_seconds: float = 0.0
    p50_seconds: float = 0.0
    p95_seconds: float = 0.0
    p99_seconds: float = 0.0
    max_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class ExecutorSaturationSnapshot:
    saturation_score: float = 0.0
    """Composite score in ``[0.0, 1.0]``. Higher = more saturated."""

    level: SaturationLevel = "calm"
    peak_utilization_ratio: float = 0.0
    backlog_velocity: float = 0.0
    """Difference between submission and completion rates — positive
    means submissions outrunning completions."""


@dataclass(frozen=True, slots=True)
class ExecutorMetricsRecord:
    """Per-executor aggregated snapshot."""

    executor_id: str
    executor_kind: str
    max_workers: int | None
    sequence: int
    utilization: ExecutorUtilizationSnapshot
    throughput: ExecutorThroughputSnapshot
    saturation: ExecutorSaturationSnapshot
    submission_latency: ExecutorLatencySnapshot
    execution_duration: ExecutorLatencySnapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "executor_id": self.executor_id,
            "executor_kind": self.executor_kind,
            "max_workers": self.max_workers,
            "sequence": self.sequence,
            "utilization": asdict(self.utilization),
            "throughput": asdict(self.throughput),
            "saturation": asdict(self.saturation),
            "submission_latency": asdict(self.submission_latency),
            "execution_duration": asdict(self.execution_duration),
        }


@dataclass(frozen=True, slots=True)
class ExecutorMetricsEngineSelfSnapshot:
    """Engine-level observability counters."""

    events_observed: int = 0
    events_ignored: int = 0
    events_dropped: int = 0
    updates_emitted: int = 0
    saturation_transitions: int = 0
    contention_detections: int = 0
    latency_spike_detections: int = 0
    tracked_executors: int = 0
    executors_evicted: int = 0
    recursion_skips: int = 0


@dataclass(frozen=True, slots=True)
class ExecutorMetricsSnapshot:
    """Top-level diagnostics snapshot."""

    executors: tuple[ExecutorMetricsRecord, ...]
    self_metrics: ExecutorMetricsEngineSelfSnapshot
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "executors": [e.to_dict() for e in self.executors],
            "self_metrics": asdict(self.self_metrics),
            "config": dict(self.config),
        }


DeltaKind = Literal[
    "updated",
    "saturation-changed",
    "contention-detected",
    "latency-spike-detected",
    "executor-finalized",
]


@dataclass(frozen=True, slots=True)
class ExecutorMetricsDelta:
    """One engine-emitted transition. Delivered to subscribers via
    :meth:`ExecutorMetricsEngine.subscribe`."""

    kind: DeltaKind
    executor_id: str
    record: ExecutorMetricsRecord
    previous_level: SaturationLevel | None = None
    new_level: SaturationLevel | None = None
