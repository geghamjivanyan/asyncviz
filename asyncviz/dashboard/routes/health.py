from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from asyncviz.dashboard.dependencies import get_health_service
from asyncviz.dashboard.health import (
    HealthService,
    HealthServiceMetricsResponse,
    HealthSnapshot,
    LivenessSnapshot,
    ReadinessSnapshot,
    RuntimeDiagnosticsSnapshot,
    is_ready,
)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthSnapshot)
async def health(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthSnapshot:
    """Return the canonical aggregated health summary.

    Runs every registered probe (CRITICAL + INFO), aggregates the
    statuses, and embeds the per-probe results. This is the
    operationally useful "give me one payload that says how the
    runtime feels" endpoint.

    HTTP status is always 200 — the body's ``status`` field is the
    machine-readable verdict. See ``/api/health/ready`` for the
    Kubernetes-style probe that maps unhealthy to 503.
    """
    return service.evaluate()


@router.get("/health/live", response_model=LivenessSnapshot)
async def health_live(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> LivenessSnapshot:
    """Liveness probe — the cheapest health check the dashboard offers.

    Does not run any subsystem probe; the existence of a 200 response
    is proof the process is alive. Suitable for Kubernetes liveness
    (failures mean restart the pod), Docker HEALTHCHECK, and CI
    smoke checks.
    """
    return service.liveness()


@router.get("/health/ready", response_model=ReadinessSnapshot)
async def health_ready(
    service: Annotated[HealthService, Depends(get_health_service)],
    response: Response,
) -> ReadinessSnapshot:
    """Readiness probe — runs CRITICAL probes; 503 when not ready.

    HTTP status reflects the aggregated verdict:
      * ``HEALTHY`` / ``DEGRADED`` → 200 (serves traffic).
      * ``STARTING`` / ``STOPPING`` / ``UNAVAILABLE`` → 503.

    The ``DEGRADED`` allowance is intentional — degraded means *some*
    non-critical subsystem is wobbly; the runtime can still serve.
    """
    snapshot = service.readiness()
    if not is_ready(snapshot.status):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return snapshot


@router.get("/health/runtime", response_model=RuntimeDiagnosticsSnapshot)
async def health_runtime(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> RuntimeDiagnosticsSnapshot:
    """Detailed runtime diagnostics for the dashboard's status panel.

    Combines the full probe set with per-subsystem operational
    counters (queue depth, replay retention bounds, websocket session
    counts, snapshot timings, warning severity tally). Always 200 —
    this is a diagnostics payload, not a probe.
    """
    return service.runtime_diagnostics()


@router.get("/health/metrics", response_model=HealthServiceMetricsResponse)
async def health_metrics(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthServiceMetricsResponse:
    """Return the health service's self-observability counters.

    Tracks how often each probe surface is called, the rate of
    degraded/unavailable evaluations, total probe failures, and the
    last / max / average evaluation timings.
    """
    snap = service.metrics_snapshot()
    return HealthServiceMetricsResponse(
        evaluations_total=snap.evaluations_total,
        liveness_checks=snap.liveness_checks,
        readiness_checks=snap.readiness_checks,
        full_checks=snap.full_checks,
        runtime_diagnostics_calls=snap.runtime_diagnostics_calls,
        degraded_evaluations=snap.degraded_evaluations,
        unavailable_evaluations=snap.unavailable_evaluations,
        probe_failures=snap.probe_failures,
        total_evaluation_ns=snap.total_evaluation_ns,
        average_evaluation_ns=snap.average_evaluation_ns,
        max_evaluation_ns=snap.max_evaluation_ns,
        last_evaluation_ns=snap.last_evaluation_ns,
    )
