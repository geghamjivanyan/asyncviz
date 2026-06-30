"""Runtime event models for the executor metrics engine.

These events are the *output* of :class:`ExecutorMetricsEngine`; raw
executor events (``asyncio.executor.*`` — see :mod:`.executor`) are
the input. The engine emits one of these whenever a per-executor
aggregate transitions in a way the dashboard cares about.

Mirrors the :mod:`.queue_metrics` event family — same shapes, same
redaction policy (no callables, no exception messages — only ids,
counters, enums, and class-name strings).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from asyncviz.runtime.events.models.base import RuntimeEvent


class _ExecutorMetricsEventBase(RuntimeEvent):
    """Shared envelope for every executor-metrics event."""

    executor_id: str
    executor_kind: str
    max_workers: int | None = None
    sequence: int = 0
    """Monotonic per-executor revision counter — every per-executor
    emission bumps it."""
    snapshot: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutorMetricsUpdatedEvent(_ExecutorMetricsEventBase):
    """Debounced snapshot of an executor's aggregated metrics."""

    event_type: Literal["asyncio.executor.metrics.updated"] = "asyncio.executor.metrics.updated"

    active_workers: int = 0
    peak_active_workers: int = 0
    utilization_ratio: float = 0.0
    mean_utilization: float = 0.0

    submissions: int = 0
    completions: int = 0
    failures: int = 0
    cancellations: int = 0
    submission_rate: float = 0.0
    completion_rate: float = 0.0
    backlog: int = 0

    mean_submission_latency_seconds: float = 0.0
    p95_submission_latency_seconds: float = 0.0
    mean_execution_duration_seconds: float = 0.0
    p95_execution_duration_seconds: float = 0.0

    saturation_score: float = 0.0
    saturation_level: str = "calm"


class ExecutorSaturationChangedEvent(_ExecutorMetricsEventBase):
    """Emitted when an executor's saturation band transitions.

    Hysteresis-gated: an executor must cross the upper threshold to
    escalate and fall below ``threshold - hysteresis`` to de-escalate.
    Prevents flicker on bouncy workloads."""

    event_type: Literal["asyncio.executor.saturation.changed"] = (
        "asyncio.executor.saturation.changed"
    )

    previous_level: str = "calm"
    new_level: str = "calm"
    saturation_score: float = 0.0
    utilization_ratio: float = 0.0
    backlog: int = 0


class ExecutorContentionDetectedEvent(_ExecutorMetricsEventBase):
    """Emitted when ``active_workers / max_workers`` first crosses the
    configured contention threshold. Leading-edge — stays silent while
    above; re-fires after a clean drop below."""

    event_type: Literal["asyncio.executor.contention.detected"] = (
        "asyncio.executor.contention.detected"
    )

    active_workers: int = 0
    max_workers: int | None = None
    utilization_ratio: float = 0.0


class ExecutorLatencySpikeDetectedEvent(_ExecutorMetricsEventBase):
    """Emitted when a single work item's submission latency exceeds
    the configured threshold. Per-executor cooldown gates re-fires."""

    event_type: Literal["asyncio.executor.latency.spike.detected"] = (
        "asyncio.executor.latency.spike.detected"
    )

    submission_latency_seconds: float = 0.0
    threshold_seconds: float = 0.0
    active_workers: int = 0


EXECUTOR_METRICS_EVENT_TYPES: tuple[str, ...] = (
    "asyncio.executor.metrics.updated",
    "asyncio.executor.saturation.changed",
    "asyncio.executor.contention.detected",
    "asyncio.executor.latency.spike.detected",
)
