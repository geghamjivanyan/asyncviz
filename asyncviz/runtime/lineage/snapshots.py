from __future__ import annotations

from asyncviz.runtime.lineage.models import LineageSnapshot
from asyncviz.runtime.lineage.tracker import LineageTracker


def snapshot_lineage(tracker: LineageTracker, task_id: str) -> LineageSnapshot | None:
    """Materialize a JSON-safe :class:`LineageSnapshot` for one task.

    Returns ``None`` when the tracker has no record of ``task_id`` — the
    HTTP layer maps that to a 404.
    """
    lineage = tracker.lineage_of(task_id)
    if lineage is None:
        return None
    return LineageSnapshot(
        task_id=lineage.task_id,
        parent_task_id=lineage.parent_task_id,
        root_task_id=lineage.root_task_id,
        depth=lineage.depth,
        ancestor_chain=list(lineage.ancestor_chain),
        child_count=lineage.child_count,
        descendants=list(tracker.descendants(task_id)),
    )
