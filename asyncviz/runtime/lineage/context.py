"""ContextVar-based lookup for the currently-executing runtime task.

A single :class:`contextvars.ContextVar` carries the asyncviz ``task_id`` of
whatever task is currently running on the loop. Asyncio's task constructor
captures the active context, so any child task spawned via the instrumented
``create_task`` inherits its parent's task_id automatically — that's the
mechanism that lets :func:`current_parent_task` return the correct id even
when ``asyncio.current_task()`` would have returned ``None`` (cross-thread
publishes, callbacks scheduled from outside the loop).

The instrumented ``create_task`` sets this var *before* allocating the new
task. The task captures the parent's context, so when it eventually runs,
calling :func:`current_runtime_task` from inside the task body returns the
new task's id — not the parent's. That's by design: the var is reassigned
inside the task wrapper before user code runs.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

_RUNTIME_TASK_ID: ContextVar[str | None] = ContextVar("asyncviz_runtime_task_id", default=None)
_PARENT_TASK_ID: ContextVar[str | None] = ContextVar("asyncviz_parent_task_id", default=None)


def current_runtime_task() -> str | None:
    """asyncviz task_id of the task currently executing on this loop.

    Returns ``None`` outside an instrumented task (root callers, threads
    that aren't running an asyncio loop, internal asyncviz code).
    """
    return _RUNTIME_TASK_ID.get()


def current_parent_task() -> str | None:
    """asyncviz task_id of the *parent* of the task currently executing.

    For root tasks this is ``None``. For nested tasks it's the parent's id —
    useful for lineage-aware logging and for the lineage tracker to record
    the relationship without consulting the registry.
    """
    return _PARENT_TASK_ID.get()


@dataclass(frozen=True, slots=True)
class LineageBinding:
    """Token returned by :func:`bind_lineage_context` so callers can reset."""

    runtime_token: object
    parent_token: object


def bind_lineage_context(task_id: str, parent_task_id: str | None) -> LineageBinding:
    """Set the lineage vars for the currently executing context.

    Called by the instrumented ``create_task`` wrapper *before* the real
    ``asyncio.create_task`` is invoked, so the child task's captured context
    points at the right ids. The wrapper resets the vars afterwards via
    :func:`reset_lineage_context`.
    """
    return LineageBinding(
        runtime_token=_RUNTIME_TASK_ID.set(task_id),
        parent_token=_PARENT_TASK_ID.set(parent_task_id),
    )


def reset_lineage_context(binding: LineageBinding) -> None:
    """Reverse :func:`bind_lineage_context`. Always paired in a try/finally."""
    _RUNTIME_TASK_ID.reset(binding.runtime_token)  # type: ignore[arg-type]
    _PARENT_TASK_ID.reset(binding.parent_token)  # type: ignore[arg-type]
