from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Iterable

from asyncviz.runtime.lineage.ancestry import (
    DEFAULT_MAX_DEPTH,
    ancestors_tuple,
    detect_cycle,
)
from asyncviz.runtime.lineage.exceptions import CyclicAncestryError
from asyncviz.runtime.lineage.graph import (
    export_descendants,
    filter_orphans,
    list_roots,
)
from asyncviz.runtime.lineage.models import LineageMetricsSnapshot, TaskLineage


class LineageTracker:
    """Authoritative parent/child registry for an AsyncViz runtime.

    Stores three flat maps:

    * ``parent_of[task_id] -> parent_task_id | None``
    * ``children_of[task_id] -> set[task_id]``
    * ``ancestors_of[task_id] -> tuple[task_id, ...]`` (closest-first)
      — cached at registration so ``depth`` and ``root`` are O(1) reads.

    The cached ancestors tuple is the source of truth for ``depth`` and
    ``root_task_id``. Mutations recompute it only for the affected task and
    its parent linkage; descendant subtrees stay stable because their
    ancestor chains terminate at their own immediate parent.

    Thread-safe. The :class:`TaskRegistry` composes a tracker and forwards
    register/unregister calls through it. All public methods are safe to
    call concurrently.
    """

    def __init__(self, *, max_depth: int = DEFAULT_MAX_DEPTH) -> None:
        self._lock = threading.RLock()
        self._max_depth = max_depth
        self._parent_of: dict[str, str | None] = {}
        self._children_of: dict[str, set[str]] = defaultdict(set)
        self._ancestors_of: dict[str, tuple[str, ...]] = {}
        self._cyclic_rejections = 0

    # ── mutations ────────────────────────────────────────────────────────
    def register(self, task_id: str, parent_task_id: str | None) -> TaskLineage:
        """Record a task and (optionally) its parent. Idempotent.

        If ``parent_task_id`` is unknown the task is treated as a root and
        ``parent_task_id`` is stored as ``None`` so subsequent late-arriving
        registrations don't try to re-parent.

        Raises :class:`CyclicAncestryError` only if the requested edge would
        close a cycle; in that case the registration is rejected and the
        previous lineage (if any) stays intact.
        """
        with self._lock:
            if task_id in self._parent_of:
                # Already registered. We don't re-parent on second register;
                # the first observation wins, keeping replays deterministic.
                return self._lineage_locked(task_id)

            if parent_task_id is not None:
                if detect_cycle(
                    parent_task_id,
                    task_id,
                    self._parent_of,
                    max_depth=self._max_depth,
                ):
                    self._cyclic_rejections += 1
                    raise CyclicAncestryError(
                        f"refusing to parent {task_id!r} under {parent_task_id!r} (cycle)"
                    )
                if parent_task_id not in self._parent_of:
                    # Parent isn't tracked yet — store the reference but treat
                    # the task as effectively a root for depth/ancestor math.
                    # This matches what the registry does for late-parent replays.
                    self._parent_of[task_id] = parent_task_id
                    self._children_of[parent_task_id].add(task_id)
                    self._ancestors_of[task_id] = ()
                    return self._lineage_locked(task_id)

                parent_ancestors = self._ancestors_of.get(parent_task_id, ())
                self._parent_of[task_id] = parent_task_id
                self._children_of[parent_task_id].add(task_id)
                self._ancestors_of[task_id] = (parent_task_id, *parent_ancestors)
            else:
                self._parent_of[task_id] = None
                self._ancestors_of[task_id] = ()

            return self._lineage_locked(task_id)

    def unregister(self, task_id: str) -> None:
        """Forget ``task_id``. Children become orphans (parent stays as a string).

        We intentionally do NOT re-parent the children to ``None`` because
        the parent reference is still semantically meaningful in events
        and snapshots; the child just loses its ancestry resolution. The
        orphan count surfaces this in metrics.
        """
        with self._lock:
            parent = self._parent_of.pop(task_id, None)
            self._ancestors_of.pop(task_id, None)
            if parent is not None:
                bucket = self._children_of.get(parent)
                if bucket is not None:
                    bucket.discard(task_id)
                    if not bucket:
                        self._children_of.pop(parent, None)
            # Orphan children: drop their cached ancestor chain so a future
            # snapshot doesn't surface a stale path.
            for child in self._children_of.pop(task_id, set()):
                self._ancestors_of[child] = ()

    def clear(self) -> None:
        with self._lock:
            self._parent_of.clear()
            self._children_of.clear()
            self._ancestors_of.clear()
            self._cyclic_rejections = 0

    # ── reads ────────────────────────────────────────────────────────────
    def lineage_of(self, task_id: str) -> TaskLineage | None:
        with self._lock:
            if task_id not in self._parent_of:
                return None
            return self._lineage_locked(task_id)

    def children(self, task_id: str) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._children_of.get(task_id, set())))

    def descendants(self, task_id: str) -> tuple[str, ...]:
        with self._lock:
            return tuple(export_descendants(task_id, self._children_of))

    def ancestors(self, task_id: str) -> tuple[str, ...]:
        with self._lock:
            return self._ancestors_of.get(task_id, ())

    def parent_of(self, task_id: str) -> str | None:
        with self._lock:
            return self._parent_of.get(task_id)

    def root_of(self, task_id: str) -> str | None:
        with self._lock:
            if task_id not in self._parent_of:
                return None
            ancestors = self._ancestors_of.get(task_id, ())
            return ancestors[-1] if ancestors else task_id

    def depth_of(self, task_id: str) -> int:
        with self._lock:
            return len(self._ancestors_of.get(task_id, ()))

    def child_count(self, task_id: str) -> int:
        with self._lock:
            return len(self._children_of.get(task_id, set()))

    def list_roots(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(list_roots(self._parent_of)))

    def __contains__(self, task_id: object) -> bool:
        if not isinstance(task_id, str):
            return False
        with self._lock:
            return task_id in self._parent_of

    def __len__(self) -> int:
        with self._lock:
            return len(self._parent_of)

    # ── re-export ancestry pieces for the registry ───────────────────────
    def recompute_ancestors(self, task_id: str) -> tuple[str, ...]:
        """Reseat the ancestor cache for ``task_id`` from a fresh walk.

        Used when external state changes (e.g. a late parent registration).
        Returns the new tuple. Not invoked on the hot path.
        """
        with self._lock:
            chain = ancestors_tuple(task_id, self._parent_of, max_depth=self._max_depth)
            self._ancestors_of[task_id] = chain
            return chain

    # ── observability ────────────────────────────────────────────────────
    def metrics_snapshot(self) -> LineageMetricsSnapshot:
        with self._lock:
            tracked = len(self._parent_of)
            roots = sum(1 for parent in self._parent_of.values() if parent is None)
            max_depth = max(
                (len(chain) for chain in self._ancestors_of.values()),
                default=0,
            )
            orphans = len(filter_orphans(self._parent_of, self._parent_of.keys()))
            return LineageMetricsSnapshot(
                tracked_tasks=tracked,
                root_tasks=roots,
                max_depth=max_depth,
                orphan_links=orphans,
                cyclic_rejections=self._cyclic_rejections,
            )

    # ── helpers ──────────────────────────────────────────────────────────
    def _lineage_locked(self, task_id: str) -> TaskLineage:
        chain = self._ancestors_of.get(task_id, ())
        root = chain[-1] if chain else task_id
        return TaskLineage(
            task_id=task_id,
            parent_task_id=self._parent_of.get(task_id),
            root_task_id=root,
            depth=len(chain),
            ancestor_chain=chain,
            child_count=len(self._children_of.get(task_id, set())),
        )

    def lineages(self, task_ids: Iterable[str]) -> dict[str, TaskLineage]:
        with self._lock:
            return {tid: self._lineage_locked(tid) for tid in task_ids if tid in self._parent_of}
