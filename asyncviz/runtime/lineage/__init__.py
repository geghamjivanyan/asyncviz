"""Canonical task lineage / ancestry tracking.

Public surface:

* :class:`LineageTracker` — the authoritative parent/child registry. One per
  runtime; composed by :class:`asyncviz.runtime.tasks.TaskRegistry`.
* :class:`TaskLineage` — value type returned by ``register`` / ``lineage_of``.
* :class:`LineageSnapshot` / :class:`LineageMetricsSnapshot` — JSON-safe
  outputs for ``/api/runtime/lineage/{task_id}`` and ``/api/runtime/metrics``.
* :func:`current_runtime_task` / :func:`current_parent_task` —
  ContextVar-backed lookups. Always valid; return ``None`` outside an
  instrumented task.
* :func:`bind_lineage_context` / :func:`reset_lineage_context` — wrapper
  primitives used by the instrumented ``asyncio.create_task``.
* exceptions — :class:`LineageError`, :class:`CyclicAncestryError`,
  :class:`OrphanTaskError`, :class:`LineageDepthExceededError`.
"""

from asyncviz.runtime.lineage.ancestry import (
    DEFAULT_MAX_DEPTH,
    ancestors_tuple,
    compute_depth,
    compute_root,
    descendants_of,
    detect_cycle,
    iter_subtree,
    roots_in,
    walk_ancestors,
)
from asyncviz.runtime.lineage.context import (
    LineageBinding,
    bind_lineage_context,
    current_parent_task,
    current_runtime_task,
    reset_lineage_context,
)
from asyncviz.runtime.lineage.exceptions import (
    CyclicAncestryError,
    LineageDepthExceededError,
    LineageError,
    OrphanTaskError,
)
from asyncviz.runtime.lineage.graph import (
    export_adjacency,
    export_descendants,
    filter_orphans,
    leaves_of,
    lineage_path,
    list_roots,
    subtree_size,
)
from asyncviz.runtime.lineage.models import (
    LineageMetricsSnapshot,
    LineageSnapshot,
    TaskLineage,
)
from asyncviz.runtime.lineage.propagation import (
    CancellationPropagationEvent,
    CancellationPropagator,
    NullPropagator,
)
from asyncviz.runtime.lineage.snapshots import snapshot_lineage
from asyncviz.runtime.lineage.tracker import LineageTracker

__all__ = [
    "DEFAULT_MAX_DEPTH",
    "CancellationPropagationEvent",
    "CancellationPropagator",
    "CyclicAncestryError",
    "LineageBinding",
    "LineageDepthExceededError",
    "LineageError",
    "LineageMetricsSnapshot",
    "LineageSnapshot",
    "LineageTracker",
    "NullPropagator",
    "OrphanTaskError",
    "TaskLineage",
    "ancestors_tuple",
    "bind_lineage_context",
    "compute_depth",
    "compute_root",
    "current_parent_task",
    "current_runtime_task",
    "descendants_of",
    "detect_cycle",
    "export_adjacency",
    "export_descendants",
    "filter_orphans",
    "iter_subtree",
    "leaves_of",
    "lineage_path",
    "list_roots",
    "reset_lineage_context",
    "roots_in",
    "snapshot_lineage",
    "subtree_size",
    "walk_ancestors",
]
