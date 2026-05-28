from __future__ import annotations

from collections.abc import Iterable

from asyncviz.runtime.tasks.models import RuntimeTask, TaskSnapshot


def snapshot_tasks(tasks: Iterable[RuntimeTask]) -> tuple[TaskSnapshot, ...]:
    """Materialize an immutable, deterministically-ordered snapshot tuple.

    Sort order: ``(created_at, task_id)`` ascending — stable across runs and
    safe for diffing in the frontend.
    """
    return tuple(
        TaskSnapshot.from_task(task)
        for task in sorted(tasks, key=lambda t: (t.created_at, t.task_id))
    )
