"""Canonical health-status enum + aggregation logic.

The single source of truth for what counts as "healthy" and how the
per-probe results are folded into one summary value. Kept in its own
module so probes can import it without circling through the service
layer.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class HealthStatus(StrEnum):
    """Canonical operational status.

    The ordering reflects severity — :func:`aggregate_status` takes the
    *worst* value across a set of checks. ``STARTING`` and ``STOPPING``
    are lifecycle transitions, not failures; they prevent a runtime
    from being marked ready but they do not mark it as unhealthy.

    Wire string values are stable; coordinate with the TypeScript
    ``HealthStatus`` type before changing them.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STARTING = "starting"
    STOPPING = "stopping"
    UNAVAILABLE = "unavailable"


#: Higher number = worse. ``aggregate_status`` picks the highest.
_SEVERITY: dict[HealthStatus, int] = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.STARTING: 1,
    HealthStatus.STOPPING: 1,
    HealthStatus.DEGRADED: 2,
    HealthStatus.UNAVAILABLE: 3,
}


def severity_of(status: HealthStatus) -> int:
    """Numeric severity for ordering / aggregation."""
    return _SEVERITY[status]


def aggregate_status(statuses: Iterable[HealthStatus]) -> HealthStatus:
    """Fold a set of statuses into one summary.

    Rules:
      * empty set → :attr:`HealthStatus.HEALTHY` (vacuously fine).
      * otherwise → the worst (highest-severity) status present.

    ``STARTING`` / ``STOPPING`` rank above ``HEALTHY`` so a runtime in
    transition is never reported as ``HEALTHY``, even if every probe
    happened to return clean. Below ``DEGRADED`` so a single bad probe
    can still dominate a transitioning runtime.
    """
    worst: HealthStatus | None = None
    worst_severity = -1
    for status in statuses:
        severity = _SEVERITY[status]
        if severity > worst_severity:
            worst = status
            worst_severity = severity
    return worst if worst is not None else HealthStatus.HEALTHY


def is_ready(status: HealthStatus) -> bool:
    """``True`` when the runtime is operational enough for traffic.

    Drives the HTTP status code on ``/api/health/ready``: ``HEALTHY`` /
    ``DEGRADED`` map to 200, every other state maps to 503. The
    ``DEGRADED`` allowance is intentional — degraded means *some*
    non-critical subsystem is wobbly, but the runtime can still serve
    requests; 503'ing in that state would cause Kubernetes to take
    pods out of rotation for cosmetic problems.
    """
    return status in {HealthStatus.HEALTHY, HealthStatus.DEGRADED}
