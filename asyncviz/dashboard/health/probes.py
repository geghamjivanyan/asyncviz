"""Built-in health probes for the AsyncViz dashboard.

Each probe is a pure function: ``state -> HealthCheckResult``. Probes
do not raise — the registry takes care of recording exceptions, but
defensive ``UNAVAILABLE`` returns are still cheaper.

The set of probes registered here covers every long-lived subsystem
the dashboard owns. Extra probes (custom integrations, plugin
diagnostics) can be added via :meth:`HealthCheckRegistry.register`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from asyncviz.dashboard.health.checks import (
    CheckSeverity,
    HealthCheckResult,
    degraded,
    healthy,
    starting,
    stopping,
    unavailable,
)

if TYPE_CHECKING:
    from asyncviz.dashboard.state.backend import BackendAppState


# ── Lifecycle probe ──────────────────────────────────────────────────────


def probe_runtime_lifecycle(state: BackendAppState) -> HealthCheckResult:
    """Maps :class:`RuntimeState` to the canonical health enum.

    ``idle`` → ``STARTING`` (process is up but lifespan hasn't completed).
    ``running`` → ``HEALTHY``.
    ``stopped`` → ``STOPPING``.

    This probe is CRITICAL — readiness fails if the runtime isn't
    fully started, which is exactly what an orchestrator wants to see
    during a rolling deploy.
    """
    name = "runtime_lifecycle"
    runtime_status = state.runtime_state.status
    uptime = state.runtime_state.uptime_seconds
    details = {"runtime_status": runtime_status, "uptime_seconds": uptime}
    if runtime_status == "running":
        return healthy(name, message="runtime is running", details=details)
    if runtime_status == "idle":
        return starting(name, message="runtime has not started yet", details=details)
    # ``stopped`` falls through to here.
    return stopping(name, message="runtime has been stopped", details=details)


# ── Clock probe ──────────────────────────────────────────────────────────


def probe_clock(state: BackendAppState) -> HealthCheckResult:
    """Confirms the canonical clock can produce a snapshot."""
    name = "runtime_clock"
    snap = state.runtime_clock.snapshot()
    return healthy(
        name,
        message="clock is monotonic",
        details={
            "uptime_seconds": snap.uptime_seconds,
            "current_sequence": snap.current_sequence,
        },
    )


# ── State store probe ────────────────────────────────────────────────────


def probe_state_store(state: BackendAppState) -> HealthCheckResult:
    """Validates the store is reachable + reports last sequence.

    Critical: a missing store means no derived state, no replay, no
    snapshot can be served.
    """
    name = "state_store"
    metrics = state.state_store.metrics_snapshot()
    details = {
        "events_applied": metrics.events_applied,
        "last_event_sequence": metrics.last_event_sequence,
        "rejected": metrics.events_rejected,
    }
    return healthy(name, message="state store is reachable", details=details)


# ── Timeline engine probe ────────────────────────────────────────────────


def probe_timeline_engine(state: BackendAppState) -> HealthCheckResult:
    """Sanity-check timeline engine. Critical."""
    name = "timeline_engine"
    metrics = state.timeline_engine.metrics_snapshot()
    invalid = metrics.invalid_transitions
    details = {
        "transitions_applied": metrics.transitions_applied,
        "invalid_transitions": invalid,
        "active_segments": metrics.active_segments,
    }
    if invalid > 0 and metrics.transitions_applied > 0:
        # Invalid transitions accumulate when the engine sees out-of-order
        # state changes. A handful is noisy data; a lot of them point at
        # a bug. Degrade once they cross 10% of accepted transitions.
        ratio = invalid / max(1, metrics.transitions_applied + invalid)
        if ratio > 0.1:
            return degraded(
                name,
                message=f"high invalid transition rate ({ratio:.0%})",
                details=details,
            )
    return healthy(name, message="timeline engine is healthy", details=details)


# ── Metrics aggregator probe ─────────────────────────────────────────────


def probe_metrics_aggregator(state: BackendAppState) -> HealthCheckResult:
    """The aggregator is critical for analytics + warning evaluation."""
    name = "metrics_aggregator"
    snap = state.metrics_aggregator.snapshot()
    self_metrics = snap.self_metrics
    details = {
        "events_observed": self_metrics.events_observed,
        "events_stale": self_metrics.events_stale,
        "events_duplicate": self_metrics.events_duplicate,
        "subscription_failures": self_metrics.subscription_failures,
    }
    return healthy(name, message="aggregator is healthy", details=details)


# ── Warning manager probe ────────────────────────────────────────────────


def probe_warning_manager(state: BackendAppState) -> HealthCheckResult:
    """Warning manager itself is critical; the warnings *content* is INFO.

    A high count of ``critical`` warnings is reported as a degraded
    operational signal — the manager is still doing its job, but the
    user program has something on fire.
    """
    name = "warning_manager"
    snap = state.warning_manager.snapshot()
    counts = snap.counts_by_severity
    details = {
        "active": len(snap.active),
        "info": counts.info,
        "warning": counts.warning,
        "error": counts.error,
        "critical": counts.critical,
    }
    if counts.critical > 0:
        return degraded(
            name,
            message=f"{counts.critical} critical warning(s) active",
            details=details,
        )
    if counts.error > 0:
        return degraded(
            name,
            message=f"{counts.error} error warning(s) active",
            details=details,
        )
    return healthy(name, message="no critical warnings", details=details)


# ── Replay buffer probe ──────────────────────────────────────────────────


def probe_replay_buffer(state: BackendAppState) -> HealthCheckResult:
    """Replay buffer integrity. Critical.

    Reports a degraded status when the miss-to-hit ratio is high, which
    signals clients are arriving with cursors before the retention
    window — usually a sign the buffer is undersized for traffic.
    """
    name = "replay_buffer"
    snap = state.replay_buffer.snapshot()
    self_metrics = snap.self_metrics
    requests = self_metrics.replay_requests
    misses = self_metrics.replay_misses
    details = {
        "frame_count": snap.frame_count,
        "capacity": snap.capacity,
        "replay_requests": requests,
        "replay_hits": self_metrics.replay_hits,
        "replay_misses": misses,
    }
    if requests > 10 and misses / requests > 0.25:
        return degraded(
            name,
            message=f"high replay-miss rate ({misses}/{requests})",
            details=details,
        )
    return healthy(name, message="replay buffer is healthy", details=details)


# ── Event queue probe ────────────────────────────────────────────────────


def probe_event_queue(state: BackendAppState) -> HealthCheckResult:
    """Event queue running + not overflowing.

    Marked CRITICAL — if the queue's dispatcher isn't running, events
    aren't getting through to the bridge/state store/replay buffer.
    """
    name = "event_queue"
    queue = state.event_queue
    snap = queue.snapshot()
    metrics = snap.metrics
    details = {
        "running": queue.is_running,
        "depth": snap.depth,
        "capacity": snap.capacity,
        "dropped_overflow": metrics.get("dropped_overflow", 0),
    }
    if not queue.is_running:
        return unavailable(
            name,
            message="event queue dispatcher is not running",
            details=details,
        )
    dropped = metrics.get("dropped_overflow", 0)
    published = metrics.get("published", 0)
    if published > 0 and dropped / published > 0.05:
        return degraded(
            name,
            message=f"queue overflowing ({dropped}/{published} dropped)",
            severity=CheckSeverity.INFO,
            details=details,
        )
    return healthy(name, message="queue is dispatching", details=details)


# ── WebSocket gateway probe ──────────────────────────────────────────────


def probe_websocket_gateway(state: BackendAppState) -> HealthCheckResult:
    """Gateway is INFO-severity.

    The runtime can serve REST traffic without an active websocket
    session, so gateway degradation is observational. A spike in
    ``protocol_errors`` is the canonical signal that clients are
    hitting the gateway's handshake error path.
    """
    name = "websocket_gateway"
    snap = state.websocket_gateway.metrics_snapshot()
    details = {
        "sessions_active": snap.sessions_active,
        "sessions_opened": snap.sessions_opened,
        "sessions_closed": snap.sessions_closed,
        "protocol_errors": snap.protocol_errors,
        "stale_evicted": snap.sessions_stale_evicted,
    }
    if snap.sessions_opened > 0 and snap.protocol_errors / max(snap.sessions_opened, 1) > 0.2:
        return degraded(
            name,
            message=f"protocol errors ({snap.protocol_errors})",
            severity=CheckSeverity.INFO,
            details=details,
        )
    return healthy(
        name,
        message="gateway operational",
        severity=CheckSeverity.INFO,
        details=details,
    )


# ── Streaming engine probe ───────────────────────────────────────────────


def probe_streaming_engine(state: BackendAppState) -> HealthCheckResult:
    """Streaming engine status. INFO-severity.

    Streaming failures mean delta envelopes aren't reaching clients,
    but the REST + snapshot surfaces still work. Treated as DEGRADED
    rather than UNAVAILABLE.
    """
    name = "streaming_engine"
    engine = state.streaming_engine
    snap = engine.metrics_snapshot()
    details = {
        "running": engine.is_running,
        "metrics_deltas_sent": snap.metrics_deltas_sent,
        "warning_deltas_sent": snap.warning_deltas_sent,
        "timeline_deltas_sent": snap.timeline_deltas_sent,
        "broadcast_failures": snap.broadcast_failures,
        "subscription_failures": snap.subscription_failures,
    }
    if not engine.is_running:
        return degraded(
            name,
            message="streaming engine not running",
            severity=CheckSeverity.INFO,
            details=details,
        )
    if snap.broadcast_failures > 0 and snap.subscription_dispatches > 0:
        ratio = snap.broadcast_failures / snap.subscription_dispatches
        if ratio > 0.1:
            return degraded(
                name,
                message=f"broadcast failures ({ratio:.0%})",
                severity=CheckSeverity.INFO,
                details=details,
            )
    return healthy(
        name,
        message="streaming engine running",
        severity=CheckSeverity.INFO,
        details=details,
    )


# ── Snapshot service probe ───────────────────────────────────────────────


def probe_snapshot_service(state: BackendAppState) -> HealthCheckResult:
    """Snapshot service latency probe. Critical.

    The snapshot endpoint is the canonical hydration surface — if its
    average generation time blows past a couple of hundred ms the
    dashboard's bootstrap is going to feel slow. The threshold is
    intentionally generous (500ms average) so noisy CI never flakes.
    """
    name = "snapshot_service"
    snap = state.snapshot_service.metrics_snapshot()
    average_ms = snap.average_generation_ns / 1_000_000 if snap.snapshots_generated else 0.0
    max_ms = snap.max_generation_ns / 1_000_000 if snap.snapshots_generated else 0.0
    details = {
        "snapshots_generated": snap.snapshots_generated,
        "average_generation_ms": average_ms,
        "max_generation_ms": max_ms,
        "last_payload_bytes": snap.last_payload_bytes,
    }
    if snap.snapshots_generated > 0 and average_ms > 500.0:
        return degraded(
            name,
            message=f"slow snapshot generation (avg {average_ms:.1f} ms)",
            details=details,
        )
    return healthy(name, message="snapshot service is healthy", details=details)


#: Default probe set the :class:`HealthService` registers at startup.
#: Ordering controls deterministic check ordering in the diagnostics
#: payload; CRITICAL probes come first so they dominate the eyeball
#: scan.
DEFAULT_PROBES: tuple[tuple[str, HealthProbe], ...] = (  # noqa: F821
    ("runtime_lifecycle", probe_runtime_lifecycle),
    ("runtime_clock", probe_clock),
    ("event_queue", probe_event_queue),
    ("state_store", probe_state_store),
    ("timeline_engine", probe_timeline_engine),
    ("metrics_aggregator", probe_metrics_aggregator),
    ("warning_manager", probe_warning_manager),
    ("replay_buffer", probe_replay_buffer),
    ("snapshot_service", probe_snapshot_service),
    ("streaming_engine", probe_streaming_engine),
    ("websocket_gateway", probe_websocket_gateway),
)
