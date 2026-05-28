"""Convenience query API on top of the store.

Mostly thin wrappers over the registry/lineage so dashboard code and tests
have one consistent surface for "what does the runtime look like right
now?" — and so adding instrumentation (counters, caches) later only needs
to touch one module.
"""

from __future__ import annotations

from collections.abc import Iterable

from asyncviz.runtime.lineage import LineageTracker, TaskLineage
from asyncviz.runtime.tasks import TaskRegistry, TaskSnapshot


class StateQueryService:
    """Read-only entry point for the store's downstream consumers."""

    __slots__ = ("_lineage", "_registry")

    def __init__(self, registry: TaskRegistry, lineage: LineageTracker) -> None:
        self._registry = registry
        self._lineage = lineage

    # ── task lookups ─────────────────────────────────────────────────────
    def get_task(self, task_id: str) -> TaskSnapshot | None:
        return self._registry.snapshot_task(task_id)

    def get_tasks(self, task_ids: Iterable[str]) -> list[TaskSnapshot]:
        out: list[TaskSnapshot] = []
        for tid in task_ids:
            snap = self._registry.snapshot_task(tid)
            if snap is not None:
                out.append(snap)
        return out

    def get_all_tasks(self) -> list[TaskSnapshot]:
        return list(self._registry.snapshot_all_tasks())

    def get_active_tasks(self) -> list[TaskSnapshot]:
        return list(self._registry.snapshot_active_tasks())

    # ── lineage ──────────────────────────────────────────────────────────
    def get_children(self, task_id: str) -> list[TaskSnapshot]:
        return [TaskSnapshot.from_task(rt) for rt in self._registry.get_children(task_id)]

    def get_descendants(self, task_id: str) -> list[TaskSnapshot]:
        return [TaskSnapshot.from_task(rt) for rt in self._registry.get_descendants(task_id)]

    def get_roots(self) -> list[TaskSnapshot]:
        return [TaskSnapshot.from_task(rt) for rt in self._registry.get_root_tasks()]

    def lineage_of(self, task_id: str) -> TaskLineage | None:
        return self._lineage.lineage_of(task_id)
