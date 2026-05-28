from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from asyncviz.runtime.tasks import TaskSnapshot


class RuntimeLineageSummary(BaseModel):
    """Lineage roll-up embedded in the state-store snapshot.

    A point-in-time view of the lineage tracker. Fully derivable from the
    registry but materialized here so a snapshot is self-describing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tracked_tasks: int
    root_tasks: int
    max_depth: int
    orphan_links: int
    cyclic_rejections: int
    roots: list[str] = Field(default_factory=list)


class RuntimeStateMetrics(BaseModel):
    """The metrics snapshot baked into :class:`RuntimeStateSnapshot`.

    Same fields the runtime metrics endpoint exposes, but reorganized for
    the state-store consumer. Frontend mirrors this 1:1.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_tasks: int
    active_tasks: int
    completed_tasks: int
    cancelled_tasks: int
    failed_tasks: int
    terminal_tasks: int
    average_duration_seconds: float | None = None
    cancellations_by_origin: dict[str, int] = Field(default_factory=dict)
    rejected_transitions: int = 0


class RuntimeStateSnapshot(BaseModel):
    """Authoritative, replay-safe derived view of the runtime.

    This is the canonical artifact emitted by
    :meth:`RuntimeStateStore.snapshot`. It is:

      * deterministic — tasks sorted by (created_at, task_id);
      * self-describing — embeds clock identity + sequence high-water mark;
      * JSON-safe — Pydantic with ``extra='forbid'`` enforces drift surfaces
        on either side of the wire.

    Field names are part of the public protocol; coordinate with the
    TypeScript ``RuntimeStateSnapshot`` definition before changing them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Bumped on incompatible shape changes. Add new optional fields freely;
    #: bump only when a consumer would have to relearn the schema.
    schema_version: int = 1

    #: Wall-clock seconds at which this snapshot was emitted.
    generated_at: float

    #: Monotonic-ns at which this snapshot was emitted. Pair this with
    #: ``last_event_monotonic_ns`` to compute "snapshot lag" if needed.
    generated_at_monotonic_ns: int

    #: Highest envelope sequence reflected in this snapshot.
    last_sequence: int

    #: ``event_id`` of the last applied event (UUID string).
    last_event_id: str | None = None

    #: Identity of the runtime that produced this snapshot.
    runtime_id: str

    #: Materialized list of every task the store knows about.
    tasks: list[TaskSnapshot] = Field(default_factory=list)

    #: Tasks indexed by state, just the task ids (small payload for diffing).
    task_ids_by_state: dict[str, list[str]] = Field(default_factory=dict)

    #: Aggregated registry metrics.
    metrics: RuntimeStateMetrics

    #: Aggregated lineage summary.
    lineage: RuntimeLineageSummary

    #: Free-form bag for projection results (e.g. ``coroutine_groups``).
    projections: dict[str, Any] = Field(default_factory=dict)

    #: Per-task transition history. Keyed by ``task_id``; each value is the
    #: ordered list of :class:`TransitionRecord` dicts the reducer chain
    #: stamped on that task. Empty when ``include_transitions=False``.
    transitions: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
