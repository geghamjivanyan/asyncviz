"""Derived task-state indexes exposed through the state store.

Mirrors the buckets the :class:`TaskRegistry` already maintains. We expose
them as a typed view so projection code reads from one place and consumers
don't have to chase internals across modules.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.tasks import TaskRegistry


@dataclass(frozen=True, slots=True)
class StateIndexView:
    """Snapshot of every state bucket the store cares about.

    Lists are sorted by ``(created_at, task_id)`` to make snapshot equality
    diff-friendly. Empty buckets stay in the dict as empty lists so
    consumers can iterate state symbols without missing keys.
    """

    active: list[str]
    waiting: list[str]
    completed: list[str]
    cancelled: list[str]
    failed: list[str]
    created: list[str]
    by_state: dict[str, list[str]]


_ACTIVE_STATES = (TaskState.CREATED, TaskState.RUNNING, TaskState.WAITING)


def build_index_view(registry: TaskRegistry) -> StateIndexView:
    """Materialize the index view from a live :class:`TaskRegistry`.

    O(n) over the registry's task map; sorts each bucket once. Reads happen
    under the registry's lock because we go through its public list APIs.
    """
    snap_all = registry.snapshot_all_tasks()

    created: list[str] = []
    running: list[str] = []
    waiting: list[str] = []
    completed: list[str] = []
    cancelled: list[str] = []
    failed: list[str] = []

    by_state: dict[str, list[str]] = {}
    for snap in snap_all:
        bucket = by_state.setdefault(snap.state.value, [])
        bucket.append(snap.task_id)
        if snap.state is TaskState.CREATED:
            created.append(snap.task_id)
        elif snap.state is TaskState.RUNNING:
            running.append(snap.task_id)
        elif snap.state is TaskState.WAITING:
            waiting.append(snap.task_id)
        elif snap.state is TaskState.COMPLETED:
            completed.append(snap.task_id)
        elif snap.state is TaskState.CANCELLED:
            cancelled.append(snap.task_id)
        elif snap.state is TaskState.FAILED:
            failed.append(snap.task_id)

    # ``snapshot_all_tasks`` already sorts by (created_at, task_id), so the
    # per-bucket lists inherit that order.
    return StateIndexView(
        active=list(_chain(created, running)),
        waiting=waiting,
        completed=completed,
        cancelled=cancelled,
        failed=failed,
        created=created,
        by_state=by_state,
    )


def _chain(*sources: Iterable[str]) -> list[str]:
    """Tiny helper — list(chain(*)) without the import noise."""
    out: list[str] = []
    for source in sources:
        out.extend(source)
    return out


def is_active_state(state: TaskState) -> bool:
    return state in _ACTIVE_STATES
