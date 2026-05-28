from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True, slots=True)
class TaskLineage:
    """Computed ancestry view for a single task.

    Returned by :meth:`LineageTracker.register` and refreshed by
    :meth:`LineageTracker.snapshot`. All fields are derived from the parent
    chain — they are *not* independently writable. The tracker is the source
    of truth.
    """

    task_id: str
    parent_task_id: str | None
    root_task_id: str
    depth: int
    ancestor_chain: tuple[str, ...]
    child_count: int

    @property
    def is_root(self) -> bool:
        return self.parent_task_id is None


class LineageMetricsSnapshot(BaseModel):
    """Aggregate ancestry view, exposed through ``/api/runtime/metrics``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tracked_tasks: int
    root_tasks: int
    max_depth: int
    orphan_links: int
    cyclic_rejections: int


class LineageSnapshot(BaseModel):
    """JSON-safe lineage record for a single task (``/api/runtime/lineage/{id}``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    parent_task_id: str | None
    root_task_id: str
    depth: int
    ancestor_chain: list[str]
    child_count: int
    descendants: list[str]
