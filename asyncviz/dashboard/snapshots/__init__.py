"""Canonical runtime snapshot architecture for AsyncViz.

Public surface:

* :class:`SnapshotService` — orchestrator that composes a deterministic
  :class:`RuntimeSnapshot` from the runtime's in-process services. The
  single hydration substrate for ``GET /api/runtime/snapshot``, replay
  checkpoints, debugger inspection, and reconnect recovery.
* :class:`RuntimeSnapshot` — the canonical hydration model. Composes
  the existing sub-snapshots (state / timeline / metrics / warnings /
  replay / queue / clock) under one consistency cursor.
* :class:`SnapshotMetadata` / :class:`SnapshotConsistency` — envelope
  metadata + the sequence-consistency contract.
* :class:`HydrationOptions` — selective-hydration knobs (every sub-
  snapshot can be turned off independently).
* :class:`SnapshotMetrics` / :class:`SnapshotMetricsSnapshot` —
  observability counters surfaced via
  ``GET /api/runtime/snapshot/metrics``.
* :const:`SNAPSHOT_PROTOCOL_VERSION` — the protocol-level version
  bumped on incompatible shape changes.
* exceptions — :class:`SnapshotError`, :class:`SnapshotUnavailableError`,
  :class:`SnapshotConsistencyError`.
"""

from asyncviz.dashboard.snapshots.exceptions import (
    SnapshotConsistencyError,
    SnapshotError,
    SnapshotUnavailableError,
)
from asyncviz.dashboard.snapshots.hydration import SnapshotService
from asyncviz.dashboard.snapshots.metrics import (
    SnapshotMetrics,
    SnapshotMetricsSnapshot,
)
from asyncviz.dashboard.snapshots.models import (
    SNAPSHOT_PROTOCOL_VERSION,
    HydrationOptions,
    RuntimeSnapshot,
    RuntimeSnapshotMetricsResponse,
    SnapshotConsistency,
    SnapshotMetadata,
)

__all__ = [
    "SNAPSHOT_PROTOCOL_VERSION",
    "HydrationOptions",
    "RuntimeSnapshot",
    "RuntimeSnapshotMetricsResponse",
    "SnapshotConsistency",
    "SnapshotConsistencyError",
    "SnapshotError",
    "SnapshotMetadata",
    "SnapshotMetrics",
    "SnapshotMetricsSnapshot",
    "SnapshotService",
    "SnapshotUnavailableError",
]
