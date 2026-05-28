"""Self-observability counters for :class:`RuntimeShutdownCoordinator`.

Records both real-time progress (current phase, last step duration)
and a final :class:`ShutdownReport` once the coordinator reaches a
terminal state. The report is intentionally small — operational
debugging data, not a full event log; the replay buffer is the place
for the latter.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from asyncviz.runtime.shutdown.status import ShutdownPhase


@dataclass(frozen=True, slots=True)
class PhaseTiming:
    """Per-phase duration record."""

    phase: ShutdownPhase
    duration_ns: int
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class ShutdownReport:
    """Immutable post-shutdown report.

    Available once the coordinator reaches :attr:`ShutdownPhase.STOPPED`
    or :attr:`ShutdownPhase.FAILED`. Surfaces what happened, how long
    each step took, and which side effects fired (forced disconnects,
    cancellation escalations, final checkpoint id).
    """

    final_phase: ShutdownPhase
    reason: str
    triggered_at_monotonic_ns: int
    finished_at_monotonic_ns: int
    total_duration_ns: int
    phase_timings: tuple[PhaseTiming, ...] = field(default_factory=tuple)
    timeouts_total: int = 0
    forced_disconnects: int = 0
    forced_cancellations: int = 0
    checkpoint_id: str | None = None
    snapshot_id: str | None = None
    final_sequence: int | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def succeeded(self) -> bool:
        return self.final_phase is ShutdownPhase.STOPPED


@dataclass(frozen=True, slots=True)
class ShutdownMetricsSnapshot:
    """Immutable view of :class:`ShutdownMetrics`."""

    current_phase: ShutdownPhase
    shutdowns_requested: int
    shutdowns_completed: int
    shutdowns_failed: int
    timeouts_total: int
    forced_disconnects: int
    forced_cancellations: int
    last_total_duration_ns: int
    max_total_duration_ns: int


class ShutdownMetrics:
    """Thread-safe counters for the shutdown coordinator.

    Distinct from :class:`ShutdownReport`: this is the *cumulative*
    view across the lifetime of the process (the dashboard can be
    started/stopped multiple times in long-running embeddings;
    counters span all of them).
    """

    __slots__ = (
        "_current_phase",
        "_forced_cancellations",
        "_forced_disconnects",
        "_last_total_duration_ns",
        "_lock",
        "_max_total_duration_ns",
        "_shutdowns_completed",
        "_shutdowns_failed",
        "_shutdowns_requested",
        "_timeouts_total",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current_phase: ShutdownPhase = ShutdownPhase.IDLE
        self._shutdowns_requested = 0
        self._shutdowns_completed = 0
        self._shutdowns_failed = 0
        self._timeouts_total = 0
        self._forced_disconnects = 0
        self._forced_cancellations = 0
        self._last_total_duration_ns = 0
        self._max_total_duration_ns = 0

    def set_phase(self, phase: ShutdownPhase) -> None:
        with self._lock:
            self._current_phase = phase

    def get_phase(self) -> ShutdownPhase:
        with self._lock:
            return self._current_phase

    def record_request(self) -> None:
        with self._lock:
            self._shutdowns_requested += 1

    def record_completion(self, report: ShutdownReport) -> None:
        with self._lock:
            if report.succeeded:
                self._shutdowns_completed += 1
            else:
                self._shutdowns_failed += 1
            self._timeouts_total += report.timeouts_total
            self._forced_disconnects += report.forced_disconnects
            self._forced_cancellations += report.forced_cancellations
            self._last_total_duration_ns = report.total_duration_ns
            if report.total_duration_ns > self._max_total_duration_ns:
                self._max_total_duration_ns = report.total_duration_ns

    def snapshot(self) -> ShutdownMetricsSnapshot:
        with self._lock:
            return ShutdownMetricsSnapshot(
                current_phase=self._current_phase,
                shutdowns_requested=self._shutdowns_requested,
                shutdowns_completed=self._shutdowns_completed,
                shutdowns_failed=self._shutdowns_failed,
                timeouts_total=self._timeouts_total,
                forced_disconnects=self._forced_disconnects,
                forced_cancellations=self._forced_cancellations,
                last_total_duration_ns=self._last_total_duration_ns,
                max_total_duration_ns=self._max_total_duration_ns,
            )

    def reset(self) -> None:
        with self._lock:
            self._current_phase = ShutdownPhase.IDLE
            self._shutdowns_requested = 0
            self._shutdowns_completed = 0
            self._shutdowns_failed = 0
            self._timeouts_total = 0
            self._forced_disconnects = 0
            self._forced_cancellations = 0
            self._last_total_duration_ns = 0
            self._max_total_duration_ns = 0
