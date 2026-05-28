"""Lineage-aware aggregation helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from asyncviz.runtime.tasks import TaskSnapshot


@dataclass(frozen=True, slots=True)
class LineageAggregateSnapshot:
    """Hierarchy-wide rollup over the current registry view."""

    root_count: int
    max_depth: int
    average_fanout: float
    largest_tree_size: int
    largest_tree_root_id: str | None
    cancellations_propagated: int


def aggregate_lineage(tasks: Iterable[TaskSnapshot]) -> LineageAggregateSnapshot:
    """Build a :class:`LineageAggregateSnapshot` from a current task snapshot.

    Pure — no I/O, no internal state. Suitable for snapshot-time computation
    where the registry's lineage tracker is already locked.
    """
    tasks = list(tasks)
    if not tasks:
        return LineageAggregateSnapshot(
            root_count=0,
            max_depth=0,
            average_fanout=0.0,
            largest_tree_size=0,
            largest_tree_root_id=None,
            cancellations_propagated=0,
        )

    root_count = sum(1 for t in tasks if t.parent_task_id is None)
    max_depth = max(t.depth for t in tasks)

    parent_counts: Counter[str] = Counter()
    for t in tasks:
        if t.parent_task_id is not None:
            parent_counts[t.parent_task_id] += 1
    average_fanout = sum(parent_counts.values()) / len(parent_counts) if parent_counts else 0.0

    by_root: defaultdict[str, int] = defaultdict(int)
    for t in tasks:
        root = t.root_task_id or t.task_id
        by_root[root] += 1
    largest_root = max(by_root, key=lambda r: by_root[r]) if by_root else None
    largest_size = by_root.get(largest_root, 0) if largest_root else 0

    # Cancellations attributed to "parent" propagation. Today the
    # cancellation engine doesn't populate this origin yet (placeholder),
    # but the rollup is ready for it.
    cancellations_propagated = sum(1 for t in tasks if t.cancellation_origin == "parent")

    return LineageAggregateSnapshot(
        root_count=root_count,
        max_depth=max_depth,
        average_fanout=average_fanout,
        largest_tree_size=largest_size,
        largest_tree_root_id=largest_root,
        cancellations_propagated=cancellations_propagated,
    )
