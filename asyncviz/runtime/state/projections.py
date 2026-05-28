"""Derived projections built on top of the registry + lineage tracker.

Each projection is a pure function over the live state. The store calls
them on demand (snapshot time) rather than maintaining incremental views,
so we can grow the projection catalog without complicating the apply path.

Performance budget: projections are O(n) over the task count. For the
dashboard's expected workload (tens of thousands of tasks) that's still
under a millisecond.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from asyncviz.runtime.lineage import LineageTracker
from asyncviz.runtime.tasks import TaskRegistry, TaskSnapshot


def lineage_tree_projection(
    tasks: list[TaskSnapshot],
    *,
    lineage: LineageTracker,
) -> dict[str, Any]:
    """Group tasks by ``root_task_id`` and emit a depth-ordered list per tree.

    The output structure::

        {
          "trees": {
            "<root_id>": {
              "root_id": "<root_id>",
              "size": <int>,
              "max_depth": <int>,
              "task_ids": [<root_id>, <child1>, <grandchild1>, ...],
            },
            ...
          },
          "orphan_task_ids": [...],
        }

    A task whose ``parent_task_id`` references a tracker-unknown id is
    surfaced in ``orphan_task_ids`` so the frontend can still display it as
    a root row without misclaiming ancestry.
    """
    trees: dict[str, dict[str, Any]] = {}
    orphan_ids: list[str] = []
    by_id: dict[str, TaskSnapshot] = {snap.task_id: snap for snap in tasks}

    for snap in tasks:
        root = snap.root_task_id or snap.task_id
        # An orphan is a task whose parent_task_id is non-null but isn't in
        # our tracker's parent_of map (filter_orphans semantics).
        if snap.parent_task_id is not None and snap.parent_task_id not in by_id:
            orphan_ids.append(snap.task_id)

        bucket = trees.setdefault(
            root,
            {
                "root_id": root,
                "size": 0,
                "max_depth": 0,
                "task_ids": [],
            },
        )
        bucket["size"] += 1
        bucket["max_depth"] = max(bucket["max_depth"], snap.depth)
        bucket["task_ids"].append(snap.task_id)

    # Stable ordering: tasks within each tree sorted by depth then created_at.
    for tree in trees.values():
        tree["task_ids"].sort(
            key=lambda tid: (
                by_id[tid].depth if tid in by_id else 0,
                by_id[tid].created_at if tid in by_id else 0.0,
                tid,
            )
        )
    _ = lineage  # reserved for future descendant-precomputation; kept for API stability
    return {"trees": trees, "orphan_task_ids": sorted(set(orphan_ids))}


def coroutine_groups_projection(tasks: list[TaskSnapshot]) -> dict[str, Any]:
    """Group tasks by ``coroutine_name`` for "where does my code spend time" views.

    Each group includes total count, terminal counts, and the average
    duration over completed tasks (cancelled / failed tasks are reported
    but excluded from the average because their semantics differ).
    """
    by_name: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "active": 0,
            "completed": 0,
            "cancelled": 0,
            "failed": 0,
            "task_ids": [],
            "completed_duration_total": 0.0,
            "completed_duration_count": 0,
        }
    )
    for snap in tasks:
        key = snap.coroutine_name or "<anonymous>"
        bucket = by_name[key]
        bucket["count"] += 1
        bucket["task_ids"].append(snap.task_id)
        match snap.state.value:
            case "completed":
                bucket["completed"] += 1
                if snap.duration_seconds is not None:
                    bucket["completed_duration_total"] += snap.duration_seconds
                    bucket["completed_duration_count"] += 1
            case "cancelled":
                bucket["cancelled"] += 1
            case "failed":
                bucket["failed"] += 1
            case _:
                bucket["active"] += 1

    # Finalize derived averages and drop the running totals from the wire shape.
    out: dict[str, Any] = {}
    for name, bucket in by_name.items():
        count = bucket["completed_duration_count"]
        total = bucket["completed_duration_total"]
        out[name] = {
            "count": bucket["count"],
            "active": bucket["active"],
            "completed": bucket["completed"],
            "cancelled": bucket["cancelled"],
            "failed": bucket["failed"],
            "task_ids": bucket["task_ids"],
            "average_completed_duration_seconds": (total / count) if count else None,
        }
    return out


def cancellations_by_origin_projection(
    registry: TaskRegistry,
) -> dict[str, list[str]]:
    """Inverted index from cancellation origin → cancelled task ids.

    Mirrors the metrics counter but lets the frontend pivot from "show me
    everything cancelled at shutdown" to the actual task list in one step.
    """
    origins = ("explicit", "shutdown", "timeout", "parent", None)
    out: dict[str, list[str]] = {}
    for origin in origins:
        tasks = registry.list_cancellations_by_origin(origin)
        if not tasks:
            continue
        key = origin if origin is not None else "unknown"
        out[key] = sorted(t.task_id for t in tasks)
    return out


def default_projections() -> Mapping[str, str]:
    """Names of the projections the store materializes by default.

    Mapped to a human-readable description so the runtime API can surface
    "what's in this snapshot" without consumers reading source code.
    """
    return {
        "lineage_tree": "Grouped task trees indexed by root_task_id.",
        "coroutine_groups": "Tasks grouped by coroutine_name with rolled-up stats.",
        "cancellations_by_origin": "Cancellation origin → task ids, sorted.",
    }
