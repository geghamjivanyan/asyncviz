"""Wire-shape Pydantic models for the health API.

These are the *only* shapes any operator / probe / orchestrator should
read against. The internal :class:`HealthCheckResult` dataclass exists
to keep the probe contract ergonomic; this module is the public
surface.

Frontend mirrors these field-for-field — drift on either side surfaces
via TypeScript strict + Pydantic ``extra='forbid'``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from asyncviz.dashboard.health.checks import CheckSeverity
from asyncviz.dashboard.health.status import HealthStatus

#: Protocol version for the canonical health envelope. Bumped on any
#: incompatible shape change to :class:`HealthSnapshot`. Frontend gates
#: on this before relying on individual fields.
HEALTH_PROTOCOL_VERSION = 1


class HealthCheckPayload(BaseModel):
    """One probe's result on the wire."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    status: HealthStatus
    severity: CheckSeverity
    message: str = ""
    latency_ns: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


class LivenessSnapshot(BaseModel):
    """Cheapest probe: the process answered.

    No subsystem inspection — every field is derived from the request
    handler itself. ``status`` is always ``HEALTHY`` for a successful
    response; the existence of this payload is the proof.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: HealthStatus = HealthStatus.HEALTHY
    protocol_version: int = HEALTH_PROTOCOL_VERSION
    generated_at: float
    generated_at_monotonic_ns: int
    process_uptime_seconds: float


class ReadinessSnapshot(BaseModel):
    """Output of ``/api/health/ready`` — readiness probe shape.

    Aggregated ``status`` is derived from every ``CRITICAL`` check.
    Non-critical checks contribute to ``degraded_count`` but never to
    the overall ``status`` here — readiness is about whether the
    runtime can serve traffic, not whether everything is perfect.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: HealthStatus
    protocol_version: int = HEALTH_PROTOCOL_VERSION
    generated_at: float
    generated_at_monotonic_ns: int
    runtime_id: str
    runtime_status: str
    runtime_uptime_seconds: float
    critical_checks: list[HealthCheckPayload] = Field(default_factory=list)
    degraded_count: int = 0
    unavailable_count: int = 0


class HealthSnapshot(BaseModel):
    """Output of ``/api/health`` — the canonical aggregated summary.

    Combines every probe (CRITICAL + INFO) under one aggregated
    ``status``. The full check list is exposed so dashboards can render
    a status grid; the ``summary`` field carries small precomputed
    counts so the dashboard doesn't have to bucket the list itself.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: HealthStatus
    protocol_version: int = HEALTH_PROTOCOL_VERSION
    generated_at: float
    generated_at_monotonic_ns: int
    runtime_id: str
    runtime_status: str
    runtime_uptime_seconds: float
    evaluation_duration_ns: int
    checks: list[HealthCheckPayload] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class RuntimeDiagnosticsSnapshot(BaseModel):
    """Output of ``/api/health/runtime`` — detailed operational diagnostics.

    This is the "give me everything I need to debug a sick runtime" payload.
    It does NOT replace the snapshot endpoint (which is structural
    hydration data); this is operational data: counters, rates,
    queue depths, retention bounds, recent rate of probe failures.

    Kept narrow — no full task lists, no full event streams. The
    snapshot endpoint exists for that.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: HealthStatus
    protocol_version: int = HEALTH_PROTOCOL_VERSION
    generated_at: float
    generated_at_monotonic_ns: int
    runtime_id: str
    runtime_status: str
    runtime_uptime_seconds: float
    process_uptime_seconds: float

    #: Aggregate-level counters across the runtime.
    tasks_total: int
    tasks_active: int
    tasks_terminal: int

    #: Queue health.
    queue_depth: int
    queue_capacity: int
    queue_dropped_overflow: int

    #: Replay health.
    replay_frame_count: int
    replay_oldest_sequence: int | None
    replay_newest_sequence: int | None
    replay_misses: int

    #: WebSocket health.
    websocket_active_sessions: int
    websocket_protocol_errors: int

    #: Streaming health.
    streaming_running: bool
    streaming_broadcast_failures: int

    #: Snapshot health.
    snapshot_average_generation_ns: float
    snapshot_max_generation_ns: int

    #: Warnings overview.
    warnings_active: int
    warnings_critical: int
    warnings_error: int
    warnings_warning: int
    warnings_info: int

    #: Probe summary.
    checks: list[HealthCheckPayload] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class HealthServiceMetricsResponse(BaseModel):
    """Wire shape of :class:`HealthMetrics` for ``GET /api/health/metrics``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluations_total: int
    liveness_checks: int
    readiness_checks: int
    full_checks: int
    runtime_diagnostics_calls: int
    degraded_evaluations: int
    unavailable_evaluations: int
    probe_failures: int
    total_evaluation_ns: int
    average_evaluation_ns: float
    max_evaluation_ns: int
    last_evaluation_ns: int
