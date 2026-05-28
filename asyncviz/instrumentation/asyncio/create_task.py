from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from asyncviz.instrumentation.asyncio.context import CancellationContext, TaskContext
from asyncviz.instrumentation.asyncio.ids import new_task_id
from asyncviz.instrumentation.asyncio.wrappers import instrument_task
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.lineage import (
    bind_lineage_context,
    current_runtime_task,
    reset_lineage_context,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("instrumentation.asyncio.create_task")

CreateTaskFn = Callable[..., asyncio.Task[Any]]


def make_instrumented_create_task(
    original: CreateTaskFn,
    *,
    bus: EventBus,
    context: TaskContext,
    cancellation_context: CancellationContext,
    runtime_id: uuid.UUID,
) -> CreateTaskFn:
    """Return a drop-in replacement for ``asyncio.create_task``.

    Semantic guarantees:
      * Signature, return type, exceptions, and naming match the original.
      * The real asyncio.Task is created **before** any instrumentation runs.
        If our wrapper code raises, the user still gets a valid task back.
      * Parent-task lookup happens *before* the new task is scheduled so
        we record causality, not coincidence.
    """

    def instrumented_create_task(
        coro: Coroutine[Any, Any, Any], **kwargs: Any
    ) -> asyncio.Task[Any]:
        parent_task: asyncio.Task[Any] | None
        try:
            parent_task = asyncio.current_task()
        except RuntimeError:
            parent_task = None

        # Allocate the asyncviz task_id now so we can stamp the ContextVar
        # *before* the real ``create_task`` captures the calling context.
        # The new task's captured context will then advertise this id as the
        # runtime-task-id; descendants spawned from inside this task can read
        # it via :func:`current_runtime_task`.
        task_id = new_task_id()
        parent_task_id = (
            context.get(parent_task) if parent_task is not None else current_runtime_task()
        )

        binding = bind_lineage_context(task_id, parent_task_id)
        try:
            task = original(coro, **kwargs)
        finally:
            reset_lineage_context(binding)

        try:
            instrument_task(
                task,
                coro,
                parent_task=parent_task,
                parent_task_id_override=parent_task_id,
                task_id=task_id,
                context=context,
                cancellation_context=cancellation_context,
                bus=bus,
                runtime_id=runtime_id,
            )
        except Exception as exc:
            logger.debug("instrumentation skipped for task: %s", exc)

        return task

    instrumented_create_task.__doc__ = getattr(original, "__doc__", None)
    instrumented_create_task.__qualname__ = getattr(
        original, "__qualname__", "instrumented_create_task"
    )
    instrumented_create_task.__name__ = getattr(original, "__name__", "create_task")
    return instrumented_create_task
