"""Probe + check-result primitives.

A *probe* is a callable that inspects one subsystem and returns a
:class:`HealthCheckResult`. Probes are first-class so they can be
registered / replaced / inspected independent of the service layer.

A probe must not raise — failures are caught and reported as an
``UNAVAILABLE`` result with the exception text in ``message``. The
registry enforces this contract on its execution path.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from asyncviz.dashboard.health.status import HealthStatus

if TYPE_CHECKING:
    from asyncviz.dashboard.state.backend import BackendAppState


class CheckSeverity(StrEnum):
    """Whether a check's failure should drag down readiness.

    * ``CRITICAL`` — failure marks the runtime as ``UNAVAILABLE``.
      Reserved for subsystems the runtime cannot operate without
      (state store, replay buffer, snapshot service, etc.).
    * ``INFO`` — failure marks the runtime as ``DEGRADED``. Used for
      observational subsystems (warnings count, websocket session
      backpressure) where the rest of the system can keep serving.

    The severity is a *probe-author* declaration; the registry maps it
    to the aggregated :class:`HealthStatus`.
    """

    CRITICAL = "critical"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    """One probe's evaluation.

    ``details`` is the operator-facing debug bag — small, JSON-safe,
    intended for the diagnostics endpoint. Keep it under a few hundred
    bytes per check; this is not the place to dump full snapshots.
    """

    name: str
    status: HealthStatus
    severity: CheckSeverity
    message: str = ""
    latency_ns: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        return self.status is HealthStatus.HEALTHY


#: Probe contract: input is the typed app state, output is a result.
HealthProbe = Callable[["BackendAppState"], HealthCheckResult]


def healthy(
    name: str,
    *,
    severity: CheckSeverity = CheckSeverity.CRITICAL,
    message: str = "ok",
    details: dict[str, Any] | None = None,
) -> HealthCheckResult:
    """Build a ``HEALTHY`` :class:`HealthCheckResult`.

    Helper so probes don't have to repeat the boilerplate. ``latency_ns``
    is stamped by the registry — probes shouldn't measure their own
    latency.
    """
    return HealthCheckResult(
        name=name,
        status=HealthStatus.HEALTHY,
        severity=severity,
        message=message,
        details=details or {},
    )


def degraded(
    name: str,
    message: str,
    *,
    severity: CheckSeverity = CheckSeverity.INFO,
    details: dict[str, Any] | None = None,
) -> HealthCheckResult:
    """Build a ``DEGRADED`` :class:`HealthCheckResult`."""
    return HealthCheckResult(
        name=name,
        status=HealthStatus.DEGRADED,
        severity=severity,
        message=message,
        details=details or {},
    )


def unavailable(
    name: str,
    message: str,
    *,
    severity: CheckSeverity = CheckSeverity.CRITICAL,
    details: dict[str, Any] | None = None,
) -> HealthCheckResult:
    """Build an ``UNAVAILABLE`` :class:`HealthCheckResult`."""
    return HealthCheckResult(
        name=name,
        status=HealthStatus.UNAVAILABLE,
        severity=severity,
        message=message,
        details=details or {},
    )


def starting(
    name: str,
    message: str = "starting",
    *,
    severity: CheckSeverity = CheckSeverity.CRITICAL,
    details: dict[str, Any] | None = None,
) -> HealthCheckResult:
    """Build a ``STARTING`` :class:`HealthCheckResult`."""
    return HealthCheckResult(
        name=name,
        status=HealthStatus.STARTING,
        severity=severity,
        message=message,
        details=details or {},
    )


def stopping(
    name: str,
    message: str = "stopping",
    *,
    severity: CheckSeverity = CheckSeverity.CRITICAL,
    details: dict[str, Any] | None = None,
) -> HealthCheckResult:
    """Build a ``STOPPING`` :class:`HealthCheckResult`."""
    return HealthCheckResult(
        name=name,
        status=HealthStatus.STOPPING,
        severity=severity,
        message=message,
        details=details or {},
    )
