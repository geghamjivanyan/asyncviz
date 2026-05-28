"""Shared reducer machinery — transition stamping, history append, metrics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state.reducers.base import ReducerContext, ReducerResult
from asyncviz.runtime.state.reducers.projections import ProjectionName
from asyncviz.runtime.state.reducers.transitions import TransitionRecord
from asyncviz.runtime.state.reducers.validation import evaluate_transition
from asyncviz.runtime.tasks.exceptions import (
    InvalidStateTransitionError,
    UnknownTaskError,
)

if TYPE_CHECKING:
    from asyncviz.runtime.tasks import RuntimeTask


def current_state_of(ctx: ReducerContext, task_id: str) -> TaskState | None:
    task = ctx.registry.get(task_id)
    return task.state if task is not None else None


def record_transition(
    ctx: ReducerContext,
    *,
    task_id: str,
    target: TaskState,
    event: RuntimeEvent,
) -> TransitionRecord:
    """Stamp a :class:`TransitionRecord` and append it to the history."""
    record = TransitionRecord(
        sequence=ctx.sequence,
        state=target,
        monotonic_ns=event.monotonic_ns,
        wall_seconds=event.timestamp,
        event_id=str(event.event_id),
        event_type=event.event_type,
    )
    ctx.history.append(task_id, record)
    return record


def reject(
    ctx: ReducerContext,
    *,
    reducer_name: str,
    reason: str,
    invalid_transition: bool = False,
    terminal_blocked: bool = False,
) -> ReducerResult:
    """Centralized rejection path so metrics stay consistent."""
    ctx.metrics.record_rejected(
        reducer_name,
        invalid_transition=invalid_transition,
        terminal_blocked=terminal_blocked,
    )
    return ReducerResult.rejected(
        reason=reason,
        invalid_transition=invalid_transition,
        terminal_blocked=terminal_blocked,
    )


def accept(
    ctx: ReducerContext,
    *,
    reducer_name: str,
    transition: TransitionRecord,
    target_state: TaskState,
    projections: tuple[ProjectionName, ...] = (
        ProjectionName.LINEAGE_TREE,
        ProjectionName.INDEX_VIEW,
    ),
) -> ReducerResult:
    """Centralized success path — projection invalidation + metrics."""
    ctx.projections.mark(*projections)
    ctx.metrics.record_applied(reducer_name, ctx.sequence)
    return ReducerResult.ok(transition=transition, target_state=target_state)


def safe_target_transition(
    ctx: ReducerContext,
    *,
    task_id: str,
    target: TaskState,
    reducer_name: str,
    event: RuntimeEvent,
    projections: tuple[ProjectionName, ...] = (
        ProjectionName.LINEAGE_TREE,
        ProjectionName.INDEX_VIEW,
    ),
) -> ReducerResult:
    """Common shape for non-creation reducers.

    Pre-validates via :func:`evaluate_transition`, then defers the actual
    mutation to ``registry.handle_event(event)``. On registry-level
    rejection (e.g. concurrent transition raced ours) the reducer surfaces
    the failure rather than partially mutating.
    """
    current = current_state_of(ctx, task_id)
    plan = evaluate_transition(current, target)
    if not plan.allowed:
        return reject(
            ctx,
            reducer_name=reducer_name,
            reason=plan.reason or "transition not allowed",
            invalid_transition=True,
            terminal_blocked=plan.terminal_blocked,
        )

    try:
        ctx.registry.handle_event(event)
    except (InvalidStateTransitionError, UnknownTaskError) as exc:
        return reject(
            ctx,
            reducer_name=reducer_name,
            reason=str(exc),
            invalid_transition=True,
        )
    # The registry can also silently no-op (e.g. it caught an
    # InvalidStateTransitionError inside its event dispatcher); confirm
    # that the post-state matches our intent before recording history.
    new_task: RuntimeTask | None = ctx.registry.get(task_id)
    if new_task is None or new_task.state is not target:
        return reject(
            ctx,
            reducer_name=reducer_name,
            reason=f"registry did not transition to {target.value}",
            invalid_transition=True,
        )

    transition = record_transition(
        ctx,
        task_id=task_id,
        target=target,
        event=event,
    )
    return accept(
        ctx,
        reducer_name=reducer_name,
        transition=transition,
        target_state=target,
        projections=projections,
    )
