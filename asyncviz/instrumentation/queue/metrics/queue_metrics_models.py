"""Typed snapshot + delta models for the queue metrics engine.

Snapshots are frozen, dataclass-based, JSON-safe via :meth:`to_dict`.
They are the wire shape returned by the diagnostics endpoint and the
in-memory shape held by per-queue state. Deltas describe one
engine-emitted transition so subscribers can react incrementally.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

#: Pressure bands. Single source of truth — the engine, the events, and
#: the diagnostics layer all use these exact strings.
PressureLevel = Literal["calm", "warning", "critical"]


@dataclass(frozen=True, slots=True)
class QueueOccupancySnapshot:
    current_size: int = 0
    peak_size: int = 0
    occupancy_ratio: float = 0.0
    mean_occupancy: float = 0.0
    sample_count: int = 0


@dataclass(frozen=True, slots=True)
class QueueThroughputSnapshot:
    put_count: int = 0
    get_count: int = 0
    put_rate: float = 0.0
    get_rate: float = 0.0
    producer_consumer_delta: int = 0
    """``put_count - get_count``; positive means producers outrunning consumers."""

    task_done_count: int = 0
    nowait_put_count: int = 0
    nowait_get_count: int = 0
    cancelled_count: int = 0


@dataclass(frozen=True, slots=True)
class QueueContentionSnapshot:
    blocked_producers: int = 0
    """Current blocked-putter count as of the last observed event."""

    blocked_consumers: int = 0
    blocked_put_count: int = 0
    """Lifetime count of blocked-put completions."""

    blocked_get_count: int = 0
    full_wait_count: int = 0
    empty_wait_count: int = 0
    cancelled_count: int = 0
    peak_blocked_producers: int = 0
    peak_blocked_consumers: int = 0


@dataclass(frozen=True, slots=True)
class QueueWaitSnapshot:
    """Bounded approximation of put / get wait-time distribution.

    Mean is exact (running average). Percentiles are reservoir-sampled,
    so they're accurate for typical workloads but explicitly best-effort
    under adversarial input.
    """

    count: int = 0
    mean_seconds: float = 0.0
    p50_seconds: float = 0.0
    p95_seconds: float = 0.0
    p99_seconds: float = 0.0
    max_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class QueuePressureSnapshot:
    pressure_score: float = 0.0
    """Composite score in ``[0.0, 1.0]``. Higher = more pressure."""

    level: PressureLevel = "calm"
    saturation_ratio: float = 0.0
    """Highest ``occupancy_ratio`` observed in the active window."""

    saturated: bool = False
    backlog_velocity: float = 0.0
    """Sign + magnitude of ``put_rate - get_rate``."""


@dataclass(frozen=True, slots=True)
class QueueMetricsRecord:
    """Per-queue aggregated snapshot."""

    queue_id: str
    queue_kind: str
    maxsize: int
    sequence: int
    occupancy: QueueOccupancySnapshot
    throughput: QueueThroughputSnapshot
    contention: QueueContentionSnapshot
    pressure: QueuePressureSnapshot
    put_wait: QueueWaitSnapshot
    get_wait: QueueWaitSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "queue_kind": self.queue_kind,
            "maxsize": self.maxsize,
            "sequence": self.sequence,
            "occupancy": asdict(self.occupancy),
            "throughput": asdict(self.throughput),
            "contention": asdict(self.contention),
            "pressure": asdict(self.pressure),
            "put_wait": asdict(self.put_wait),
            "get_wait": asdict(self.get_wait),
        }


@dataclass(frozen=True, slots=True)
class QueueMetricsEngineSelfSnapshot:
    """Engine-level observability counters."""

    events_observed: int = 0
    events_ignored: int = 0
    events_dropped: int = 0
    updates_emitted: int = 0
    pressure_transitions: int = 0
    contention_detections: int = 0
    saturation_detections: int = 0
    tracked_queues: int = 0
    queues_evicted: int = 0
    """Number of queues we refused to track because we hit
    ``max_tracked_queues``."""

    recursion_skips: int = 0


@dataclass(frozen=True, slots=True)
class QueueMetricsSnapshot:
    """Top-level diagnostics snapshot."""

    queues: tuple[QueueMetricsRecord, ...]
    self_metrics: QueueMetricsEngineSelfSnapshot
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "queues": [q.to_dict() for q in self.queues],
            "self_metrics": asdict(self.self_metrics),
            "config": dict(self.config),
        }


DeltaKind = Literal[
    "updated",
    "pressure-changed",
    "contention-detected",
    "saturation-detected",
    "queue-finalized",
]


@dataclass(frozen=True, slots=True)
class QueueMetricsDelta:
    """One engine-emitted transition. Subscribers receive these via
    :meth:`QueueMetricsEngine.subscribe`."""

    kind: DeltaKind
    queue_id: str
    record: QueueMetricsRecord
    previous_level: PressureLevel | None = None
    new_level: PressureLevel | None = None
