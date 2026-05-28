"""Orchestrator that fronts the health endpoints.

``HealthService.evaluate(...)`` is the single entrypoint every route
calls — readiness, liveness, full, and diagnostics all delegate here.
The service owns the registry, the metrics counter, and the small
amount of glue that turns probe results into the canonical Pydantic
shapes.

Probes themselves live in ``probes.py``; new probes register via
``service.registry.register(...)`` from extensions / tests.
"""

from __future__ import annotations

import threading
from time import monotonic_ns
from typing import TYPE_CHECKING

from asyncviz.dashboard.health.checks import (
    CheckSeverity,
    HealthCheckResult,
)
from asyncviz.dashboard.health.metrics import (
    HealthMetrics,
    HealthMetricsSnapshot,
)
from asyncviz.dashboard.health.models import (
    HEALTH_PROTOCOL_VERSION,
    HealthCheckPayload,
    HealthSnapshot,
    LivenessSnapshot,
    ReadinessSnapshot,
    RuntimeDiagnosticsSnapshot,
)
from asyncviz.dashboard.health.probes import DEFAULT_PROBES
from asyncviz.dashboard.health.registry import HealthCheckRegistry
from asyncviz.dashboard.health.status import HealthStatus, aggregate_status

if TYPE_CHECKING:
    from asyncviz.dashboard.state.backend import BackendAppState


class HealthService:
    """Runs probes and assembles canonical health payloads.

    Thread-safe. The probe-run path takes the registry's own lock; the
    metrics counter takes its own. The service itself doesn't add a
    third — probe results are stateless on the service side.
    """

    def __init__(
        self,
        *,
        state: BackendAppState,
        registry: HealthCheckRegistry | None = None,
        register_defaults: bool = True,
    ) -> None:
        self._state = state
        self._registry = registry or HealthCheckRegistry()
        self._metrics = HealthMetrics()
        self._process_started_monotonic_ns = monotonic_ns()
        self._lock = threading.Lock()
        if register_defaults:
            for name, probe in DEFAULT_PROBES:
                self._registry.register(name, probe)

    # ── identity ─────────────────────────────────────────────────────
    @property
    def registry(self) -> HealthCheckRegistry:
        return self._registry

    @property
    def metrics(self) -> HealthMetrics:
        return self._metrics

    def metrics_snapshot(self) -> HealthMetricsSnapshot:
        return self._metrics.snapshot()

    @property
    def process_uptime_seconds(self) -> float:
        return (monotonic_ns() - self._process_started_monotonic_ns) / 1_000_000_000

    # ── shared evaluation helpers ────────────────────────────────────
    def _run_all(self) -> tuple[list[HealthCheckResult], int, int]:
        """Run every probe; return ``(results, failures, duration_ns)``."""
        started = monotonic_ns()
        results, failures = self._registry.run(self._state)
        duration = monotonic_ns() - started
        statuses = [r.status for r in results]
        degraded = HealthStatus.DEGRADED in statuses
        unavailable = HealthStatus.UNAVAILABLE in statuses
        self._metrics.record_evaluation(
            duration_ns=duration,
            degraded=degraded,
            unavailable=unavailable,
            probe_failures=failures,
        )
        return results, failures, duration

    # ── endpoints ────────────────────────────────────────────────────
    def liveness(self) -> LivenessSnapshot:
        """The cheapest probe — just confirms the process is responding.

        Does not run any probe. Used by Kubernetes/Docker as the
        liveness probe — failing this means restart the pod, so it
        must never block on subsystem state.
        """
        self._metrics.record_liveness()
        clock_snap = self._state.runtime_clock.snapshot()
        return LivenessSnapshot(
            protocol_version=HEALTH_PROTOCOL_VERSION,
            generated_at=clock_snap.wall_now_seconds,
            generated_at_monotonic_ns=clock_snap.monotonic_now_ns,
            process_uptime_seconds=self.process_uptime_seconds,
        )

    def readiness(self) -> ReadinessSnapshot:
        """Run CRITICAL probes only; aggregate into a readiness verdict."""
        self._metrics.record_readiness()
        results, _failures, _duration = self._run_all()
        critical = [r for r in results if r.severity is CheckSeverity.CRITICAL]
        status = aggregate_status(r.status for r in critical)
        degraded = sum(1 for r in results if r.status is HealthStatus.DEGRADED)
        unavailable = sum(1 for r in results if r.status is HealthStatus.UNAVAILABLE)
        clock_snap = self._state.runtime_clock.snapshot()
        return ReadinessSnapshot(
            status=status,
            protocol_version=HEALTH_PROTOCOL_VERSION,
            generated_at=clock_snap.wall_now_seconds,
            generated_at_monotonic_ns=clock_snap.monotonic_now_ns,
            runtime_id=str(clock_snap.runtime_id),
            runtime_status=self._state.runtime_state.status,
            runtime_uptime_seconds=self._state.runtime_state.uptime_seconds,
            critical_checks=[_to_payload(r) for r in critical],
            degraded_count=degraded,
            unavailable_count=unavailable,
        )

    def evaluate(self) -> HealthSnapshot:
        """Run every probe; assemble the canonical full health snapshot."""
        self._metrics.record_full_check()
        results, _failures, duration = self._run_all()
        status = aggregate_status(r.status for r in results)
        summary = _summarize(results)
        clock_snap = self._state.runtime_clock.snapshot()
        return HealthSnapshot(
            status=status,
            protocol_version=HEALTH_PROTOCOL_VERSION,
            generated_at=clock_snap.wall_now_seconds,
            generated_at_monotonic_ns=clock_snap.monotonic_now_ns,
            runtime_id=str(clock_snap.runtime_id),
            runtime_status=self._state.runtime_state.status,
            runtime_uptime_seconds=self._state.runtime_state.uptime_seconds,
            evaluation_duration_ns=duration,
            checks=[_to_payload(r) for r in results],
            summary=summary,
        )

    def runtime_diagnostics(self) -> RuntimeDiagnosticsSnapshot:
        """Run every probe + decorate with operational counters.

        Bigger payload than ``evaluate()`` — meant for the in-dashboard
        diagnostics panel, where operators want a single page that
        answers "is the runtime sick, and where?".
        """
        self._metrics.record_runtime_diagnostics()
        results, _failures, _duration = self._run_all()
        status = aggregate_status(r.status for r in results)
        summary = _summarize(results)
        clock_snap = self._state.runtime_clock.snapshot()
        state = self._state

        # Per-subsystem counters — pulled here, not in the probes, so the
        # probe set stays composable. The probes signal status; this is
        # the operational-data layer.
        queue_snap = state.event_queue.snapshot()
        replay_snap = state.replay_buffer.snapshot()
        gateway_snap = state.websocket_gateway.metrics_snapshot()
        streaming_snap = state.streaming_engine.metrics_snapshot()
        snapshot_metrics = state.snapshot_service.metrics_snapshot()
        warnings_snap = state.warning_manager.snapshot()
        task_metrics = state.task_registry.metrics_snapshot()

        return RuntimeDiagnosticsSnapshot(
            status=status,
            protocol_version=HEALTH_PROTOCOL_VERSION,
            generated_at=clock_snap.wall_now_seconds,
            generated_at_monotonic_ns=clock_snap.monotonic_now_ns,
            runtime_id=str(clock_snap.runtime_id),
            runtime_status=state.runtime_state.status,
            runtime_uptime_seconds=state.runtime_state.uptime_seconds,
            process_uptime_seconds=self.process_uptime_seconds,
            tasks_total=task_metrics.total_tasks,
            tasks_active=task_metrics.active_tasks,
            tasks_terminal=task_metrics.terminal_tasks,
            queue_depth=queue_snap.depth,
            queue_capacity=queue_snap.capacity,
            queue_dropped_overflow=queue_snap.metrics.get("dropped_overflow", 0),
            replay_frame_count=replay_snap.frame_count,
            replay_oldest_sequence=replay_snap.oldest_sequence,
            replay_newest_sequence=replay_snap.newest_sequence,
            replay_misses=replay_snap.self_metrics.replay_misses,
            websocket_active_sessions=gateway_snap.sessions_active,
            websocket_protocol_errors=gateway_snap.protocol_errors,
            streaming_running=state.streaming_engine.is_running,
            streaming_broadcast_failures=streaming_snap.broadcast_failures,
            snapshot_average_generation_ns=snapshot_metrics.average_generation_ns,
            snapshot_max_generation_ns=snapshot_metrics.max_generation_ns,
            warnings_active=len(warnings_snap.active),
            warnings_critical=warnings_snap.counts_by_severity.critical,
            warnings_error=warnings_snap.counts_by_severity.error,
            warnings_warning=warnings_snap.counts_by_severity.warning,
            warnings_info=warnings_snap.counts_by_severity.info,
            checks=[_to_payload(r) for r in results],
            summary=summary,
        )


def _to_payload(result: HealthCheckResult) -> HealthCheckPayload:
    return HealthCheckPayload(
        name=result.name,
        status=result.status,
        severity=result.severity,
        message=result.message,
        latency_ns=result.latency_ns,
        details=result.details,
    )


def _summarize(results: list[HealthCheckResult]) -> dict[str, int]:
    """Bucket counts so the dashboard doesn't have to re-bucket the list.

    Keys are the :class:`HealthStatus` string values; values are the
    number of checks in that bucket. ``checks_total`` is the total.
    """
    summary: dict[str, int] = {status.value: 0 for status in HealthStatus}
    for result in results:
        summary[result.status.value] += 1
    summary["checks_total"] = len(results)
    return summary
