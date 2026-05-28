from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from asyncviz.runtime.events.models.enums import WarningSeverity


class ActiveWarning(BaseModel):
    """A currently-open warning record.

    Immutable on the wire. Internally the :class:`RuntimeWarningManager`
    holds mutable working state and produces fresh :class:`ActiveWarning`
    instances on every snapshot.

    Field order is part of the public protocol — coordinate with the
    TypeScript ``ActiveWarning`` definition.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    warning_id: str
    warning_key: str
    warning_type: str
    severity: WarningSeverity
    message: str
    detector: str
    created_sequence: int | None
    created_monotonic_ns: int
    created_at_wall: float
    last_observed_sequence: int | None
    last_observed_monotonic_ns: int
    last_observed_wall: float
    occurrence_count: int
    resolved: bool
    resolved_sequence: int | None = None
    resolved_monotonic_ns: int | None = None
    resolved_at_wall: float | None = None
    expired: bool = False
    related_task_ids: list[str] = Field(default_factory=list)
    lineage_root_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    runtime_id: str | None = None


class WarningSeverityCounts(BaseModel):
    """Severity-bucketed counts of currently active warnings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    info: int = 0
    warning: int = 0
    error: int = 0
    critical: int = 0


class WarningSelfMetricsModel(BaseModel):
    """The manager's view of itself — observability for observability."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    detectors_registered: int
    evaluations_run: int
    detector_failures: int
    warnings_emitted: int
    warnings_resolved: int
    warnings_expired: int
    dedup_suppressions: int
    snapshots_emitted: int
    subscription_dispatches: int
    subscription_failures: int
    last_event_sequence: int


class WarningSnapshot(BaseModel):
    """Authoritative warnings view emitted by :meth:`RuntimeWarningManager.snapshot`.

    Mirror this exactly in the TypeScript ``WarningSnapshot`` interface.
    Pydantic uses ``extra='forbid'`` so drift on either side surfaces in CI.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    generated_at: float
    generated_at_monotonic_ns: int
    runtime_id: str
    last_sequence: int

    active: list[ActiveWarning] = Field(default_factory=list)
    resolved: list[ActiveWarning] = Field(default_factory=list)
    counts_by_severity: WarningSeverityCounts
    counts_by_type: dict[str, int] = Field(default_factory=dict)
    self_metrics: WarningSelfMetricsModel


class WarningDeltaModel(BaseModel):
    """JSON-safe view of a :class:`WarningDelta` for wire transport."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    warning: ActiveWarning
    change: str  # "activated" | "updated" | "resolved" | "expired" | "deduplicated"
    sequence: int | None
    last_sequence: int
