"""Per-executor aggregated state.

Owns the utilization tracker + throughput counters + latency digests +
saturation scorer for a single executor. The engine routes raw
executor events here based on ``executor_id`` and asks for a snapshot
when it needs to emit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from asyncviz.instrumentation.executor.metrics.executor_metrics_configuration import (
    ExecutorMetricsConfig,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_models import (
    ExecutorMetricsRecord,
    SaturationLevel,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_saturation import (
    SaturationScorer,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_statistics import (
    LatencyDigest,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_throughput import (
    ThroughputCounters,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_utilization import (
    UtilizationTracker,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_windows import (
    UtilizationWindow,
)
from asyncviz.runtime.events.models.executor import (
    ExecutorRegisteredEvent,
    ExecutorWorkCancelledEvent,
    ExecutorWorkCompletedEvent,
    ExecutorWorkFailedEvent,
    ExecutorWorkStartedEvent,
    ExecutorWorkSubmittedEvent,
)


@dataclass(frozen=True, slots=True)
class ApplyOutcome:
    """What changed after :meth:`ExecutorAggregateState.apply_event`."""

    accepted: bool = False
    events_since_last_emission: int = 0
    saturation_entered: bool = False
    saturation_exited: bool = False
    contention_edge: bool = False
    """``True`` when active/max ratio just crossed the contention
    threshold from below."""

    latency_spike: bool = False
    """``True`` when this submission's queue latency exceeded the
    configured spike threshold (with cooldown gating done by the
    engine)."""


@dataclass(slots=True)
class ExecutorAggregateState:
    executor_id: str
    executor_kind: str
    max_workers: int | None
    config: ExecutorMetricsConfig
    revision: int = 0
    last_emitted_revision: int = 0
    last_emit_monotonic: float = 0.0
    last_latency_spike_monotonic: float = 0.0
    last_emitted_level: SaturationLevel = "calm"

    utilization: UtilizationTracker = field(init=False)
    throughput: ThroughputCounters = field(init=False)
    submission_latency: LatencyDigest = field(init=False)
    execution_duration: LatencyDigest = field(init=False)
    saturation: SaturationScorer = field(init=False)
    finalized: bool = False
    _last_contention_above: bool = False

    def __post_init__(self) -> None:
        self.utilization = UtilizationTracker(
            window=UtilizationWindow(capacity=self.config.utilization_window_size),
            max_workers=self.max_workers,
        )
        self.throughput = ThroughputCounters(
            window_seconds=self.config.throughput_window_seconds,
        )
        self.submission_latency = LatencyDigest(
            capacity=self.config.latency_reservoir_size,
        )
        self.execution_duration = LatencyDigest(
            capacity=self.config.latency_reservoir_size,
        )
        self.saturation = SaturationScorer(config=self.config)

    # ── apply ─────────────────────────────────────────────────────────

    def apply_event(self, event: Any, *, monotonic_seconds: float) -> ApplyOutcome:
        if self.finalized:
            return ApplyOutcome(accepted=False)
        self.revision += 1
        latency_spike = False

        if isinstance(event, ExecutorRegisteredEvent):
            # Late max_workers correction — the registered event carries
            # the executor's worker cap. If the registry initially saw a
            # different value (e.g. None on the default executor before
            # the loop allocated it), update here.
            if isinstance(event.max_workers, int) and event.max_workers > 0:
                self.utilization.update_max_workers(event.max_workers)
                self.max_workers = event.max_workers
            self.executor_kind = event.executor_kind or self.executor_kind
        elif isinstance(event, ExecutorWorkSubmittedEvent):
            self.throughput.record_submission(monotonic_seconds=monotonic_seconds)
        elif isinstance(event, ExecutorWorkStartedEvent):
            self.utilization.increment()
            if event.submission_latency_seconds is not None:
                self.submission_latency.observe(event.submission_latency_seconds)
                if event.submission_latency_seconds >= self.config.latency_spike_threshold_seconds:
                    latency_spike = True
        elif isinstance(event, ExecutorWorkCompletedEvent):
            self.utilization.decrement()
            self.throughput.record_completion(monotonic_seconds=monotonic_seconds)
            if event.duration_seconds is not None:
                self.execution_duration.observe(event.duration_seconds)
        elif isinstance(event, ExecutorWorkFailedEvent):
            self.utilization.decrement()
            self.throughput.record_failure(monotonic_seconds=monotonic_seconds)
            if event.duration_seconds is not None:
                self.execution_duration.observe(event.duration_seconds)
        elif isinstance(event, ExecutorWorkCancelledEvent):
            # Cancelled work that never started doesn't decrement
            # active_workers (we only incremented on start). Cancellations
            # after start would have already gone through completed/failed
            # in the engine wrapper.
            self.throughput.record_cancellation(monotonic_seconds=monotonic_seconds)
            if event.duration_seconds is not None:
                self.execution_duration.observe(event.duration_seconds)
        else:
            return ApplyOutcome(
                accepted=True,
                events_since_last_emission=self.revision - self.last_emitted_revision,
            )

        # Contention edge: active/max ratio crossed configured threshold.
        contention_edge = False
        if self.max_workers and self.max_workers > 0:
            ratio = self.utilization.active_workers / self.max_workers
            above = ratio >= self.config.contention_active_worker_ratio
            if above and not self._last_contention_above:
                contention_edge = True
            self._last_contention_above = above

        # Saturation transition + tracking.
        throughput_snap = self.throughput.snapshot(monotonic_seconds=monotonic_seconds)
        latency_snap = self.submission_latency.snapshot()
        prev_level = self.saturation.level
        self.saturation.evaluate(
            utilization_ratio=(
                self.utilization.active_workers / self.max_workers
                if self.max_workers and self.max_workers > 0
                else 0.0
            ),
            max_workers=self.max_workers,
            backlog=throughput_snap.backlog,
            submission_rate=throughput_snap.submission_rate,
            completion_rate=throughput_snap.completion_rate,
            mean_submission_latency=latency_snap.mean_seconds,
        )
        saturation_entered = (
            prev_level != self.saturation.level
            and self.saturation.level in {"warning", "critical"}
        )
        saturation_exited = (
            prev_level != self.saturation.level and self.saturation.level == "calm"
        )

        return ApplyOutcome(
            accepted=True,
            events_since_last_emission=self.revision - self.last_emitted_revision,
            saturation_entered=saturation_entered,
            saturation_exited=saturation_exited,
            contention_edge=contention_edge,
            latency_spike=latency_spike,
        )

    # ── snapshot ──────────────────────────────────────────────────────

    def snapshot(self, *, monotonic_seconds: float | None = None) -> ExecutorMetricsRecord:
        throughput_snap = self.throughput.snapshot(monotonic_seconds=monotonic_seconds)
        utilization_snap = self.utilization.snapshot()
        latency_snap = self.submission_latency.snapshot()
        saturation_snap = self.saturation.evaluate(
            utilization_ratio=utilization_snap.utilization_ratio,
            max_workers=self.max_workers,
            backlog=throughput_snap.backlog,
            submission_rate=throughput_snap.submission_rate,
            completion_rate=throughput_snap.completion_rate,
            mean_submission_latency=latency_snap.mean_seconds,
        )
        return ExecutorMetricsRecord(
            executor_id=self.executor_id,
            executor_kind=self.executor_kind,
            max_workers=self.max_workers,
            sequence=self.revision,
            utilization=utilization_snap,
            throughput=throughput_snap,
            saturation=saturation_snap,
            submission_latency=latency_snap,
            execution_duration=self.execution_duration.snapshot(),
        )

    def mark_emitted(self, *, monotonic_seconds: float) -> None:
        self.last_emitted_revision = self.revision
        self.last_emit_monotonic = monotonic_seconds

    def mark_latency_spike_emitted(self, *, monotonic_seconds: float) -> None:
        self.last_latency_spike_monotonic = monotonic_seconds

    def can_emit_latency_spike(self, *, monotonic_seconds: float) -> bool:
        if self.last_latency_spike_monotonic == 0.0:
            return True
        elapsed = monotonic_seconds - self.last_latency_spike_monotonic
        return elapsed >= self.config.latency_spike_min_interval_seconds

    def finalize(self) -> None:
        self.finalized = True
