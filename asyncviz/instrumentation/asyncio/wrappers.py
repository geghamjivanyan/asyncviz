from __future__ import annotations

import asyncio
import uuid
from collections.abc import Coroutine
from typing import Any

from asyncviz.instrumentation.asyncio.context import CancellationContext, TaskContext
from asyncviz.instrumentation.asyncio.ids import new_task_id
from asyncviz.instrumentation.asyncio.lifecycle import attach_done_callback
from asyncviz.instrumentation.asyncio.metadata import (
    extract_coroutine_name,
    extract_task_name,
)
from asyncviz.runtime.clock import get_runtime_clock
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models import TaskCreatedEvent
from asyncviz.utils.logging import get_logger

logger = get_logger("instrumentation.asyncio.wrappers")


def instrument_task(
    task: asyncio.Task[Any],
    coro: Coroutine[Any, Any, Any],
    *,
    parent_task: asyncio.Task[Any] | None,
    context: TaskContext,
    cancellation_context: CancellationContext,
    bus: EventBus,
    runtime_id: uuid.UUID,
    task_id: str | None = None,
    parent_task_id_override: str | None = None,
) -> None:
    """Attach AsyncViz instrumentation to an already-created asyncio task.

    Captures both wall-clock (``time.time()``) and monotonic
    (``time.monotonic()``) start timestamps. The monotonic value is what we
    measure duration against — clock-drift safe and never negative.

    ``cancellation_context`` is shared across all tasks under the patcher;
    the done-callback consults it to attribute the cancellation origin.

    ``task_id`` may be pre-allocated by the caller (the instrumented
    ``create_task`` wrapper does this so it can also stamp the lineage
    ContextVar before the asyncio task captures the calling context).
    """
    if task_id is None:
        task_id = new_task_id()
    context.register(task, task_id)

    coroutine_name = extract_coroutine_name(coro)
    task_name = extract_task_name(task)
    parent_task_id = (
        parent_task_id_override if parent_task_id_override is not None else context.get(parent_task)
    )
    clock = get_runtime_clock()
    started_at = clock.now()
    started_at_monotonic_ns = clock.monotonic_ns()

    bus.publish(
        TaskCreatedEvent(
            task_id=task_id,
            parent_task_id=parent_task_id,
            coroutine_name=coroutine_name,
            task_name=task_name,
            runtime_id=runtime_id,
            source="instrumentation",
        )
    )

    attach_done_callback(
        task,
        task_id=task_id,
        bus=bus,
        runtime_id=runtime_id,
        started_at=started_at,
        started_at_monotonic_ns=started_at_monotonic_ns,
        coroutine_name=coroutine_name,
        task_name=task_name,
        cancellation_context=cancellation_context,
    )
