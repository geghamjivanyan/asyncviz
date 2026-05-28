"""Wire-shape Pydantic models for the shutdown coordinator.

Frontend dashboards subscribe to the status surface to render the
shutdown banner / reconnect guidance. The wire shapes mirror the
internal dataclasses (:class:`ShutdownPhase`, :class:`ShutdownReport`,
:class:`PhaseTiming`) field-for-field.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from asyncviz.runtime.shutdown.status import ShutdownPhase

#: Bumped on incompatible shape changes to :class:`ShutdownStatusResponse`.
SHUTDOWN_PROTOCOL_VERSION = 1


class PhaseTimingPayload(BaseModel):
    """One :class:`PhaseTiming` on the wire."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase: ShutdownPhase
    duration_ns: int
    timed_out: bool = False


class ShutdownReportPayload(BaseModel):
    """Wire shape of :class:`ShutdownReport`.

    Available once the coordinator reaches a terminal phase
    (``STOPPED`` or ``FAILED``); embedded in
    :class:`ShutdownStatusResponse` when available, ``None`` otherwise.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    final_phase: ShutdownPhase
    reason: str
    triggered_at_monotonic_ns: int
    finished_at_monotonic_ns: int
    total_duration_ns: int
    phase_timings: list[PhaseTimingPayload] = Field(default_factory=list)
    timeouts_total: int = 0
    forced_disconnects: int = 0
    forced_cancellations: int = 0
    checkpoint_id: str | None = None
    snapshot_id: str | None = None
    final_sequence: int | None = None
    errors: list[str] = Field(default_factory=list)


class ShutdownStatusResponse(BaseModel):
    """Output of ``GET /api/runtime/shutdown``.

    ``phase`` is the live phase the coordinator is in. ``report`` is
    only populated after a terminal phase — frontend code reads it to
    render the post-mortem panel.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol_version: int = SHUTDOWN_PROTOCOL_VERSION
    phase: ShutdownPhase
    requested: bool
    in_progress: bool
    completed: bool
    report: ShutdownReportPayload | None = None


class ShutdownMetricsResponse(BaseModel):
    """Wire shape of :class:`ShutdownMetricsSnapshot`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    current_phase: ShutdownPhase
    shutdowns_requested: int
    shutdowns_completed: int
    shutdowns_failed: int
    timeouts_total: int
    forced_disconnects: int
    forced_cancellations: int
    last_total_duration_ns: int
    max_total_duration_ns: int
