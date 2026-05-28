from __future__ import annotations

import uuid
from typing import Any

from asyncviz.runtime.events.models.enums import EventSource, WarningSeverity
from asyncviz.runtime.events.models.metrics import MetricEvent
from asyncviz.runtime.events.models.runtime import (
    LoopBlockedEvent,
    RuntimeStartedEvent,
    RuntimeStoppedEvent,
)
from asyncviz.runtime.events.models.task import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
)
from asyncviz.runtime.events.models.warnings import WarningEvent


def create_task_created(
    *,
    task_id: str,
    parent_task_id: str | None = None,
    coroutine_name: str | None = None,
    task_name: str | None = None,
    runtime_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> TaskCreatedEvent:
    return TaskCreatedEvent(
        task_id=task_id,
        parent_task_id=parent_task_id,
        coroutine_name=coroutine_name,
        task_name=task_name,
        runtime_id=runtime_id or uuid.uuid4(),
        source=EventSource.INSTRUMENTATION.value,
        metadata=metadata or {},
    )


def create_task_completed(
    *,
    task_id: str,
    duration_seconds: float | None = None,
    parent_task_id: str | None = None,
    coroutine_name: str | None = None,
    task_name: str | None = None,
    runtime_id: uuid.UUID | None = None,
) -> TaskCompletedEvent:
    return TaskCompletedEvent(
        task_id=task_id,
        parent_task_id=parent_task_id,
        coroutine_name=coroutine_name,
        task_name=task_name,
        duration_seconds=duration_seconds,
        runtime_id=runtime_id or uuid.uuid4(),
        source=EventSource.INSTRUMENTATION.value,
    )


def create_task_cancelled(
    *,
    task_id: str,
    duration_seconds: float | None = None,
    runtime_id: uuid.UUID | None = None,
) -> TaskCancelledEvent:
    return TaskCancelledEvent(
        task_id=task_id,
        duration_seconds=duration_seconds,
        runtime_id=runtime_id or uuid.uuid4(),
        source=EventSource.INSTRUMENTATION.value,
    )


def create_task_failed(
    *,
    task_id: str,
    exception_type: str | None = None,
    exception_message: str | None = None,
    duration_seconds: float | None = None,
    runtime_id: uuid.UUID | None = None,
) -> TaskFailedEvent:
    return TaskFailedEvent(
        task_id=task_id,
        exception_type=exception_type,
        exception_message=exception_message,
        duration_seconds=duration_seconds,
        runtime_id=runtime_id or uuid.uuid4(),
        source=EventSource.INSTRUMENTATION.value,
    )


def create_runtime_started(*, runtime_id: uuid.UUID | None = None) -> RuntimeStartedEvent:
    return RuntimeStartedEvent(
        runtime_id=runtime_id or uuid.uuid4(),
        source=EventSource.LIFECYCLE.value,
    )


def create_runtime_stopped(
    *,
    uptime_seconds: float = 0.0,
    runtime_id: uuid.UUID | None = None,
) -> RuntimeStoppedEvent:
    return RuntimeStoppedEvent(
        uptime_seconds=uptime_seconds,
        runtime_id=runtime_id or uuid.uuid4(),
        source=EventSource.LIFECYCLE.value,
    )


def create_loop_blocked(
    *,
    blocked_seconds: float,
    task_id: str | None = None,
    runtime_id: uuid.UUID | None = None,
) -> LoopBlockedEvent:
    return LoopBlockedEvent(
        blocked_seconds=blocked_seconds,
        task_id=task_id,
        runtime_id=runtime_id or uuid.uuid4(),
        source=EventSource.INSTRUMENTATION.value,
    )


def create_runtime_warning(
    *,
    message: str,
    severity: WarningSeverity = WarningSeverity.WARNING,
    category: str | None = None,
    metadata: dict[str, Any] | None = None,
    runtime_id: uuid.UUID | None = None,
) -> WarningEvent:
    return WarningEvent(
        message=message,
        severity=severity,
        category=category,
        metadata=metadata or {},
        runtime_id=runtime_id or uuid.uuid4(),
        source=EventSource.RUNTIME.value,
    )


def create_runtime_metric(
    *,
    name: str,
    value: float,
    unit: str | None = None,
    tags: dict[str, str] | None = None,
    runtime_id: uuid.UUID | None = None,
) -> MetricEvent:
    return MetricEvent(
        name=name,
        value=value,
        unit=unit,
        tags=tags or {},
        runtime_id=runtime_id or uuid.uuid4(),
        source=EventSource.RUNTIME.value,
    )
