"""Canonical hydration models for :class:`SnapshotService`.

These models are the public hydration contract surfaced by
``GET /api/runtime/snapshot`` and embedded in the websocket reconnect
flow. Field names and shapes are part of the protocol — coordinate
with the TypeScript ``RuntimeSnapshot`` interface before changing
anything here.

Design rules:

* Each sub-snapshot is the *same* Pydantic model the source service
  already emits. There is no parallel serialization path — the
  canonical snapshot is a deterministic envelope around the existing
  building blocks. That keeps the schema_version surface coherent
  across the platform.
* :class:`SnapshotMetadata` carries the only fields a consumer needs
  to validate compatibility and to bridge into incremental streaming
  (``last_sequence`` is the cursor a client picks up from after
  hydration).
* The model is ``frozen=True, extra='forbid'``: drift on either side
  of the wire surfaces in CI rather than at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from asyncviz.runtime.clock import ClockSnapshot
from asyncviz.runtime.metrics import RuntimeMetricsAggregateSnapshot
from asyncviz.runtime.queue import QueueSnapshotResponse
from asyncviz.runtime.replay import ReplaySnapshot
from asyncviz.runtime.state import RuntimeStateSnapshot
from asyncviz.runtime.timeline import TimelineSnapshot
from asyncviz.runtime.warnings import WarningSnapshot

#: Bumped on every incompatible change to :class:`RuntimeSnapshot`. New
#: optional sub-snapshots may be added without a bump; a bump signals a
#: consumer must relearn the schema.
SNAPSHOT_PROTOCOL_VERSION = 1


@dataclass(frozen=True, slots=True)
class HydrationOptions:
    """Knobs that select which sub-snapshots to materialize.

    Defaults produce the *full* canonical snapshot — the same shape
    used for fresh-eyes frontend hydration. Filtered snapshots are an
    optimization, not a separate protocol.
    """

    include_state: bool = True
    include_timeline: bool = True
    include_metrics: bool = True
    include_warnings: bool = True
    include_replay: bool = True
    include_queue: bool = True
    include_projections: bool = True
    include_transitions: bool = True
    evaluate_warnings: bool = True
    timeline_track_kind: str = "task"
    since_sequence: int | None = None  # future-use; see SnapshotService

    @property
    def is_full(self) -> bool:
        """True when every sub-snapshot is being materialized.

        Used by the observability layer to label snapshots as full vs.
        filtered without enumerating each toggle.
        """
        return all(
            (
                self.include_state,
                self.include_timeline,
                self.include_metrics,
                self.include_warnings,
                self.include_replay,
                self.include_queue,
                self.include_projections,
                self.include_transitions,
            )
        )


class SnapshotConsistency(BaseModel):
    """Consistency-cursor metadata describing what the snapshot reflects.

    A snapshot is a logically-consistent view *at* ``last_sequence``:
    every sub-snapshot was captured under the snapshot-service lock
    after every in-flight event up to ``last_sequence`` had been
    applied. Clients use these fields to:

    * decide whether to fast-forward via incremental streaming (when
      the live ``last_sequence`` has advanced past this one);
    * cross-check replay buffer compatibility (``oldest_retained_sequence``
      vs. ``last_sequence``);
    * detect a runtime restart (``runtime_id`` mismatch).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    last_sequence: int
    last_event_id: str | None = None
    generated_at_monotonic_ns: int
    generated_at: float
    oldest_retained_sequence: int | None = None
    newest_retained_sequence: int | None = None
    replay_window_hit: bool = True


class SnapshotMetadata(BaseModel):
    """Envelope metadata describing this snapshot's identity + cursor.

    Frontend hydration code reads this *first*: if ``runtime_id`` does
    not match its cached runtime, it discards the cached state and
    rebuilds. ``snapshot_version`` is the protocol version, distinct
    from individual sub-snapshots' ``schema_version`` fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_version: int = SNAPSHOT_PROTOCOL_VERSION
    snapshot_id: str
    runtime_id: str
    generated_at: float
    generated_at_monotonic_ns: int
    generation_duration_ns: int
    payload_bytes: int
    is_full: bool
    included_sources: list[str] = Field(default_factory=list)
    skipped_sources: list[str] = Field(default_factory=list)


class RuntimeSnapshot(BaseModel):
    """The canonical, replay-safe, hydration-ready runtime snapshot.

    Composition rules:

    * ``metadata`` + ``consistency`` are always present.
    * Each ``*_snapshot`` field is the same Pydantic model the source
      service emits. They are optional only when the matching
      :class:`HydrationOptions` toggle is off; the full canonical
      hydration payload has all of them populated.
    * ``hints`` is the future-extensibility bag — selective hydration
      cursors, debug flags, etc. Kept narrow today so the wire shape
      stays stable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: SnapshotMetadata
    consistency: SnapshotConsistency

    clock: ClockSnapshot
    state: RuntimeStateSnapshot | None = None
    timeline: TimelineSnapshot | None = None
    metrics: RuntimeMetricsAggregateSnapshot | None = None
    warnings: WarningSnapshot | None = None
    replay: ReplaySnapshot | None = None
    queue: QueueSnapshotResponse | None = None

    #: Future-extensibility surface. Today this is empty; reserved for
    #: things like ``{"since_sequence": ..., "selective_topics": [...]}``
    #: once selective hydration lands.
    hints: dict[str, Any] = Field(default_factory=dict)


class RuntimeSnapshotMetricsResponse(BaseModel):
    """Wire shape of :class:`SnapshotMetrics` for ``GET /api/runtime/snapshot/metrics``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshots_generated: int
    full_snapshots: int
    filtered_snapshots: int
    total_generation_ns: int
    average_generation_ns: float
    max_generation_ns: int
    last_generation_ns: int
    last_payload_bytes: int
    max_payload_bytes: int
    sources_skipped: int
    consistency_errors: int
