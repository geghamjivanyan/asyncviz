"""Typed configuration for the executor metrics engine.

Mirrors :class:`QueueMetricsConfig`. Knobs are conservative so the
engine adds negligible overhead on high-throughput executor workloads.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutorMetricsConfig:
    """Knobs for :class:`ExecutorMetricsEngine`."""

    # ── rolling-window cadence ────────────────────────────────────────

    throughput_window_seconds: int = 30
    """Window size for the submission / completion rate meters."""

    utilization_window_size: int = 256
    """Bounded ring of recent ``active_workers`` samples for the
    rolling mean."""

    latency_reservoir_size: int = 256
    """Reservoir capacity for per-executor submission + execution
    latency digests."""

    # ── emission gating ───────────────────────────────────────────────

    emit_updated: bool = True
    """``False`` mutes the debounced ``metrics.updated`` event."""

    emit_saturation: bool = True
    emit_contention: bool = True
    emit_latency_spike: bool = True

    updated_min_interval_seconds: float = 1.0
    """Lower bound on the gap between two ``metrics.updated`` events
    for one executor."""

    updated_min_event_delta: int = 16
    """Skip ``metrics.updated`` emission when fewer than this many
    raw events have been observed since the last emission. Pairs with
    the time-based bound — whichever trips first."""

    # ── saturation scoring ────────────────────────────────────────────

    saturation_warning_threshold: float = 0.7
    """Saturation score above which an executor is ``warning``."""

    saturation_critical_threshold: float = 0.9
    """Saturation score above which an executor is ``critical``."""

    saturation_hysteresis: float = 0.05
    """Required margin to de-escalate. Prevents flicker on bouncy
    saturation scores."""

    # ── contention edge detection ────────────────────────────────────

    contention_active_worker_ratio: float = 0.9
    """Active-worker / max-worker ratio that triggers a
    ``contention.detected`` leading-edge event."""

    # ── latency spike detection ───────────────────────────────────────

    latency_spike_threshold_seconds: float = 0.25
    """Submission latency (queue time) above which a single work
    item triggers a ``latency.spike.detected`` event."""

    latency_spike_min_interval_seconds: float = 0.5
    """Per-executor cooldown for latency-spike events so a string of
    submissions on a saturated pool doesn't spam the bus."""

    # ── back-pressure / safety ────────────────────────────────────────

    max_tracked_executors: int = 1024
    """Hard cap on the per-executor state map."""

    enable_tracing: bool = False
    """When ``True``, the engine appends every transition to the
    trace ring."""


DEFAULT_EXECUTOR_METRICS_CONFIG = ExecutorMetricsConfig()
