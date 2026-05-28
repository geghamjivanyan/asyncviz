"""Canonical health + readiness API for AsyncViz.

Public surface:

* :class:`HealthService` — orchestrator that fronts every health
  endpoint. Owns the :class:`HealthCheckRegistry` and the
  :class:`HealthMetrics` counter.
* :class:`HealthStatus` — canonical operational status enum
  (``HEALTHY``, ``DEGRADED``, ``STARTING``, ``STOPPING``,
  ``UNAVAILABLE``).
* :class:`HealthCheckResult` / :class:`CheckSeverity` — probe contract.
* :class:`HealthCheckRegistry` — pluggable probe ordering.
* Pydantic wire models — :class:`HealthSnapshot`,
  :class:`LivenessSnapshot`, :class:`ReadinessSnapshot`,
  :class:`RuntimeDiagnosticsSnapshot`, :class:`HealthCheckPayload`,
  :class:`HealthServiceMetricsResponse`.
* :class:`HealthMetrics` / :class:`HealthMetricsSnapshot` — self-
  observability counters.
* :const:`HEALTH_PROTOCOL_VERSION` — bumped on incompatible shape
  changes.
* exceptions — :class:`HealthError`, :class:`DuplicateProbeError`,
  :class:`CheckExecutionError`.

Built-in probes live in :mod:`asyncviz.dashboard.health.probes` and
are registered by default when constructing :class:`HealthService`.
"""

from asyncviz.dashboard.health.checks import (
    CheckSeverity,
    HealthCheckResult,
    HealthProbe,
    degraded,
    healthy,
    starting,
    stopping,
    unavailable,
)
from asyncviz.dashboard.health.exceptions import (
    CheckExecutionError,
    DuplicateProbeError,
    HealthError,
)
from asyncviz.dashboard.health.metrics import (
    HealthMetrics,
    HealthMetricsSnapshot,
)
from asyncviz.dashboard.health.models import (
    HEALTH_PROTOCOL_VERSION,
    HealthCheckPayload,
    HealthServiceMetricsResponse,
    HealthSnapshot,
    LivenessSnapshot,
    ReadinessSnapshot,
    RuntimeDiagnosticsSnapshot,
)
from asyncviz.dashboard.health.registry import HealthCheckRegistry
from asyncviz.dashboard.health.service import HealthService
from asyncviz.dashboard.health.status import (
    HealthStatus,
    aggregate_status,
    is_ready,
    severity_of,
)

__all__ = [
    "HEALTH_PROTOCOL_VERSION",
    "CheckExecutionError",
    "CheckSeverity",
    "DuplicateProbeError",
    "HealthCheckPayload",
    "HealthCheckRegistry",
    "HealthCheckResult",
    "HealthError",
    "HealthMetrics",
    "HealthMetricsSnapshot",
    "HealthProbe",
    "HealthService",
    "HealthServiceMetricsResponse",
    "HealthSnapshot",
    "HealthStatus",
    "LivenessSnapshot",
    "ReadinessSnapshot",
    "RuntimeDiagnosticsSnapshot",
    "aggregate_status",
    "degraded",
    "healthy",
    "is_ready",
    "severity_of",
    "starting",
    "stopping",
    "unavailable",
]
