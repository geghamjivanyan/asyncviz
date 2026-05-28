"""Typed configuration for the queue metrics engine.

Knobs are intentionally conservative so the engine can be enabled on
high-throughput runtimes without measurable overhead. Per-deployment
adjustment lives here so adapters can override one value without
patching the engine's internals.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueueMetricsConfig:
    """Knobs for :class:`QueueMetricsEngine`."""

    # ── rolling-window cadence ────────────────────────────────────────

    throughput_window_seconds: int = 30
    """Window size for the put/get rate meters. Mirrors the runtime
    metrics aggregator's default so dashboards can correlate."""

    occupancy_window_size: int = 256
    """Number of recent occupancy samples retained for the rolling
    mean. Bounded so per-queue state stays flat."""

    wait_reservoir_size: int = 256
    """Reservoir size for the per-queue put/get wait digests. Anything
    larger erodes the low-overhead promise; smaller hurts P99 accuracy."""

    # ── emission gating ───────────────────────────────────────────────

    emit_updated: bool = True
    """``False`` mutes the periodic / debounced ``metrics.updated`` event."""

    emit_pressure: bool = True
    emit_contention: bool = True
    emit_saturation: bool = True

    updated_min_interval_seconds: float = 1.0
    """Lower bound on the gap between two ``metrics.updated`` events for
    one queue. Debounces a hot queue without losing the last value."""

    updated_min_event_delta: int = 16
    """Skip ``metrics.updated`` emission when fewer than this many raw
    queue events have been observed since the last emission. Pairs with
    the time-based bound — whichever trips first."""

    # ── pressure scoring ──────────────────────────────────────────────

    pressure_warning_threshold: float = 0.65
    """Pressure score above which a queue is ``warning``."""

    pressure_critical_threshold: float = 0.85
    """Pressure score above which a queue is ``critical``."""

    pressure_hysteresis: float = 0.05
    """Required margin to de-escalate. A critical queue must drop below
    ``critical_threshold - hysteresis`` to fall back to warning, and so
    on. Prevents flicker on bouncy pressure scores."""

    # ── saturation detection ──────────────────────────────────────────

    saturation_threshold: float = 0.9
    """``occupancy_ratio`` at which a saturation event fires."""

    saturation_recovery_threshold: float = 0.75
    """``occupancy_ratio`` below which the engine arms the next
    saturation event. Hysteresis to prevent retrigger storms."""

    # ── contention detection ──────────────────────────────────────────

    contention_blocked_threshold: int = 1
    """Number of blocked producers OR consumers needed to declare
    contention. Leading-edge — a transition from below to at-or-above
    the threshold fires one event."""

    # ── back-pressure / safety ────────────────────────────────────────

    max_tracked_queues: int = 4096
    """Hard cap on the per-queue state map. Beyond this we stop
    accepting new queues but keep updating existing ones. Prevents
    leak-driven unbounded growth in pathological runtimes."""

    enable_tracing: bool = False
    """When ``True``, the engine appends every transition to the trace
    ring buffer. Off in production; tests + diagnostics scripts flip it."""


DEFAULT_QUEUE_METRICS_CONFIG = QueueMetricsConfig()
