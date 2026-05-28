from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReplayFrameModel(BaseModel):
    """Wire shape for one :class:`ReplayFrame`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int
    event_id: str
    event_type: str
    monotonic_ns: int
    wall_seconds: float
    runtime_id: str
    task_id: str | None = None
    parent_task_id: str | None = None
    payload: dict[str, Any]


class ReplayWindowModel(BaseModel):
    """The exact slice of replay frames returned by a query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_since: int
    requested_end: int | None
    hit: bool
    oldest_available_sequence: int | None
    newest_available_sequence: int | None
    frames: list[ReplayFrameModel] = Field(default_factory=list)


class ReplayCheckpointModel(BaseModel):
    """Wire shape for one :class:`ReplayCheckpoint`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    checkpoint_id: str
    sequence: int
    monotonic_ns: int
    wall_seconds: float
    runtime_id: str
    state: dict[str, Any] | None = None
    timeline: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    warnings: dict[str, Any] | None = None
    label: str | None = None


class ReplaySelfMetricsModel(BaseModel):
    """The buffer's view of itself — observability for observability."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    frames_appended: int
    frames_evicted: int
    replay_requests: int
    replay_hits: int
    replay_misses: int
    checkpoints_created: int
    reconstructions_completed: int
    subscription_dispatches: int
    subscription_failures: int


class ReplaySnapshot(BaseModel):
    """Authoritative buffer snapshot.

    Mirror this exactly in the TypeScript ``ReplaySnapshot`` interface.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    generated_at: float
    generated_at_monotonic_ns: int
    runtime_id: str
    capacity: int
    frame_count: int
    oldest_sequence: int | None
    newest_sequence: int | None
    oldest_evicted_sequence: int | None
    checkpoints: list[ReplayCheckpointModel] = Field(default_factory=list)
    latest_checkpoint: ReplayCheckpointModel | None = None
    self_metrics: ReplaySelfMetricsModel


class ReplayBatchModel(BaseModel):
    """A replay window plus an optional fast-forward checkpoint.

    The wire-side result of a reconnect/since-sequence request. If
    ``checkpoint`` is non-null, the consumer should apply the checkpoint
    *first* and then play ``frames`` over it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    window: ReplayWindowModel
    checkpoint: ReplayCheckpointModel | None = None
