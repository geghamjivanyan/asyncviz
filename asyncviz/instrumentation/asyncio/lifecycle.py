from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import Any

from asyncviz.instrumentation.asyncio.context import CancellationContext
from asyncviz.runtime.clock import get_runtime_clock
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskFailedEvent,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("instrumentation.asyncio.lifecycle")


def attach_done_callback(
    task: asyncio.Task[Any],
    *,
    task_id: str,
    bus: EventBus,
    runtime_id: uuid.UUID,
    started_at: float,
    started_at_monotonic_ns: int,
    coroutine_name: str | None = None,
    task_name: str | None = None,
    cancellation_context: CancellationContext | None = None,
) -> None:
    """Attach a done-callback that emits the terminal event for ``task``.

    Timing semantics:
      * ``started_at``              — wall-clock at task creation (for display).
      * ``started_at_monotonic_ns`` — monotonic-ns at creation (for duration math).
      * ``duration_seconds`` on the emitted event is computed from
        ``clock.duration_since_ns(started_at_monotonic_ns).seconds`` so it is
        nanosecond-precise and always ``>= 0``.

    ``cancellation_context`` is consulted only on the cancelled branch — it
    tells us whether to stamp ``cancellation_origin = "shutdown"`` (set by
    the dashboard lifespan during teardown) or ``"explicit"`` (any other
    cancellation we observe via ``task.cancelling()``). The field stays
    ``None`` when no context is provided.
    """

    def _done(t: asyncio.Task[Any]) -> None:
        try:
            _publish_terminal_event(
                t,
                task_id=task_id,
                bus=bus,
                runtime_id=runtime_id,
                started_at=started_at,
                started_at_monotonic_ns=started_at_monotonic_ns,
                coroutine_name=coroutine_name,
                task_name=task_name,
                cancellation_context=cancellation_context,
            )
        except Exception as exc:
            logger.debug("terminal-event emission failed for task %s: %s", task_id, exc)

    task.add_done_callback(_done)


def _publish_terminal_event(
    task: asyncio.Task[Any],
    *,
    task_id: str,
    bus: EventBus,
    runtime_id: uuid.UUID,
    started_at: float,
    started_at_monotonic_ns: int,
    coroutine_name: str | None,
    task_name: str | None,
    cancellation_context: CancellationContext | None,
) -> None:
    clock = get_runtime_clock()
    completed_at = clock.now()
    duration = clock.duration_since_ns(started_at_monotonic_ns).seconds

    common = {
        "task_id": task_id,
        "coroutine_name": coroutine_name,
        "task_name": task_name,
        "created_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": duration,
        "runtime_id": runtime_id,
        "source": "instrumentation",
    }

    # task.cancelled() must be checked first — task.exception() raises
    # CancelledError on a cancelled task.
    if task.cancelled():
        origin = cancellation_context.attribute(task) if cancellation_context is not None else None
        bus.publish(TaskCancelledEvent(**common, cancellation_origin=origin))
        return

    exc: BaseException | None = None
    with contextlib.suppress(Exception):
        exc = task.exception()
    if exc is not None:
        bus.publish(
            TaskFailedEvent(
                **common,
                exception_type=type(exc).__name__,
                exception_message=_safe_str(exc),
            )
        )
        return

    bus.publish(TaskCompletedEvent(**common))


def _safe_str(exc: BaseException) -> str:
    """Stringify an exception defensively — some types raise on ``str(e)``."""
    try:
        text = str(exc)
    except Exception:
        text = repr(exc)
    return text if len(text) <= 1024 else text[:1024] + "…"
