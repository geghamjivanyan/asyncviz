"""Rebuild the engine state from a stream of transition records.

The state store's :class:`TransitionHistory` keeps every per-task
transition; the engine can therefore re-derive its entire working set
from history alone — no events required.

We expose two entry points: :func:`replay_history` (consume an arbitrary
iterable) and :func:`replay_state_store` (drive everything from a live
:class:`RuntimeStateStore`). Both are deterministic.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state import RuntimeStateStore
from asyncviz.runtime.state.reducers import TransitionRecord

if TYPE_CHECKING:
    from asyncviz.runtime.timeline.engine import TimelineSegmentEngine


def replay_history(
    engine: TimelineSegmentEngine,
    records_by_task: dict[str, Iterable[TransitionRecord]],
    *,
    metadata_by_task: dict[str, dict[str, str | int | None]] | None = None,
) -> int:
    """Drive ``engine`` through every record. Returns the count applied.

    ``metadata_by_task`` carries the per-task fields the engine cannot
    derive from a single :class:`TransitionRecord` (parent / coroutine /
    task name / depth / root). The state store has all of these on the
    :class:`RuntimeTask`; tests can pass an empty dict and the engine will
    fall back to defaults.
    """
    metadata_by_task = metadata_by_task or {}
    applied = 0
    flattened: list[tuple[str, TransitionRecord]] = []
    for task_id, records in records_by_task.items():
        for record in records:
            flattened.append((task_id, record))
    # Replay in (sequence, monotonic_ns, task_id) order — matches the wire
    # order the live system would have produced.
    flattened.sort(
        key=lambda pair: (
            pair[1].sequence if pair[1].sequence is not None else -1,
            pair[1].monotonic_ns,
            pair[0],
        )
    )

    for task_id, record in flattened:
        metadata = metadata_by_task.get(task_id, {})
        outcome = engine.apply_transition(
            task_id=task_id,
            target=record.state,
            sequence=record.sequence,
            monotonic_ns=record.monotonic_ns,
            wall_seconds=record.wall_seconds,
            parent_task_id=metadata.get("parent_task_id"),  # type: ignore[arg-type]
            coroutine_name=metadata.get("coroutine_name"),  # type: ignore[arg-type]
            task_name=metadata.get("task_name"),  # type: ignore[arg-type]
            depth=metadata.get("depth", 0),  # type: ignore[arg-type]
            root_task_id=metadata.get("root_task_id"),  # type: ignore[arg-type]
        )
        if outcome.applied:
            applied += 1
    return applied


def replay_state_store(
    engine: TimelineSegmentEngine,
    store: RuntimeStateStore,
) -> int:
    """Re-derive the engine from ``store``'s registry + transition history."""
    records_by_task: dict[str, Iterable[TransitionRecord]] = {}
    metadata_by_task: dict[str, dict[str, str | int | None]] = {}
    for task_id in store.history.task_ids():
        records_by_task[task_id] = store.history.get(task_id)
        task = store.registry.get(task_id)
        if task is not None:
            metadata_by_task[task_id] = {
                "parent_task_id": task.parent_task_id,
                "coroutine_name": task.coroutine_name,
                "task_name": task.task_name,
                "depth": task.depth,
                "root_task_id": task.root_task_id,
            }
    return replay_history(engine, records_by_task, metadata_by_task=metadata_by_task)


def is_terminal_state(state: TaskState) -> bool:
    return state in {TaskState.COMPLETED, TaskState.CANCELLED, TaskState.FAILED}
