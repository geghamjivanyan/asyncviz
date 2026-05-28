from __future__ import annotations

from typing import Any

from asyncviz.runtime.events.models.base import GenericEvent, RuntimeEvent
from asyncviz.runtime.events.models.enums import EventType
from asyncviz.runtime.events.models.executor import (
    ExecutorRegisteredEvent,
    ExecutorWorkCancelledEvent,
    ExecutorWorkCompletedEvent,
    ExecutorWorkFailedEvent,
    ExecutorWorkStartedEvent,
    ExecutorWorkSubmittedEvent,
)
from asyncviz.runtime.events.models.executor_metrics import (
    ExecutorContentionDetectedEvent,
    ExecutorLatencySpikeDetectedEvent,
    ExecutorMetricsUpdatedEvent,
    ExecutorSaturationChangedEvent,
)
from asyncviz.runtime.events.models.gather import (
    GatherCancelledEvent,
    GatherChildAttachedEvent,
    GatherChildCompletedEvent,
    GatherCompletedEvent,
    GatherCreatedEvent,
    GatherFailedEvent,
    GatherWaitStartedEvent,
)
from asyncviz.runtime.events.models.metrics import MetricEvent
from asyncviz.runtime.events.models.queue import (
    QueueCancelledEvent,
    QueueCreatedEvent,
    QueueEmptyWaitEvent,
    QueueFullWaitEvent,
    QueueGetEvent,
    QueuePutEvent,
    QueueTaskDoneEvent,
)
from asyncviz.runtime.events.models.queue_metrics import (
    QueueContentionDetectedEvent,
    QueueMetricsUpdatedEvent,
    QueuePressureChangedEvent,
    QueueSaturationDetectedEvent,
)
from asyncviz.runtime.events.models.runtime import (
    LoopBlockedEvent,
    RuntimeStartedEvent,
    RuntimeStoppedEvent,
)
from asyncviz.runtime.events.models.semaphore import (
    SemaphoreAcquiredEvent,
    SemaphoreAcquireStartedEvent,
    SemaphoreContentionDetectedEvent,
    SemaphoreCreatedEvent,
    SemaphoreReleasedEvent,
    SemaphoreWaitCancelledEvent,
)
from asyncviz.runtime.events.models.task import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
    TaskResumedEvent,
    TaskStartedEvent,
    TaskWaitingEvent,
)
from asyncviz.runtime.events.models.warnings import WarningEvent


class EventValidationError(ValueError):
    """Raised when :func:`from_dict` cannot reconstruct a valid event."""


EVENT_REGISTRY: dict[str, type[RuntimeEvent]] = {
    EventType.TASK_CREATED: TaskCreatedEvent,
    EventType.TASK_STARTED: TaskStartedEvent,
    EventType.TASK_WAITING: TaskWaitingEvent,
    EventType.TASK_RESUMED: TaskResumedEvent,
    EventType.TASK_COMPLETED: TaskCompletedEvent,
    EventType.TASK_CANCELLED: TaskCancelledEvent,
    EventType.TASK_FAILED: TaskFailedEvent,
    EventType.LOOP_BLOCKED: LoopBlockedEvent,
    EventType.QUEUE_CREATED: QueueCreatedEvent,
    EventType.QUEUE_PUT: QueuePutEvent,
    EventType.QUEUE_GET: QueueGetEvent,
    EventType.QUEUE_FULL_WAIT: QueueFullWaitEvent,
    EventType.QUEUE_EMPTY_WAIT: QueueEmptyWaitEvent,
    EventType.QUEUE_TASK_DONE: QueueTaskDoneEvent,
    EventType.QUEUE_CANCELLED: QueueCancelledEvent,
    EventType.QUEUE_METRICS_UPDATED: QueueMetricsUpdatedEvent,
    EventType.QUEUE_PRESSURE_CHANGED: QueuePressureChangedEvent,
    EventType.QUEUE_CONTENTION_DETECTED: QueueContentionDetectedEvent,
    EventType.QUEUE_SATURATION_DETECTED: QueueSaturationDetectedEvent,
    EventType.SEMAPHORE_CREATED: SemaphoreCreatedEvent,
    EventType.SEMAPHORE_ACQUIRE_STARTED: SemaphoreAcquireStartedEvent,
    EventType.SEMAPHORE_ACQUIRED: SemaphoreAcquiredEvent,
    EventType.SEMAPHORE_RELEASED: SemaphoreReleasedEvent,
    EventType.SEMAPHORE_CONTENTION_DETECTED: SemaphoreContentionDetectedEvent,
    EventType.SEMAPHORE_WAIT_CANCELLED: SemaphoreWaitCancelledEvent,
    EventType.GATHER_CREATED: GatherCreatedEvent,
    EventType.GATHER_CHILD_ATTACHED: GatherChildAttachedEvent,
    EventType.GATHER_WAIT_STARTED: GatherWaitStartedEvent,
    EventType.GATHER_CHILD_COMPLETED: GatherChildCompletedEvent,
    EventType.GATHER_COMPLETED: GatherCompletedEvent,
    EventType.GATHER_CANCELLED: GatherCancelledEvent,
    EventType.GATHER_FAILED: GatherFailedEvent,
    EventType.EXECUTOR_REGISTERED: ExecutorRegisteredEvent,
    EventType.EXECUTOR_WORK_SUBMITTED: ExecutorWorkSubmittedEvent,
    EventType.EXECUTOR_WORK_STARTED: ExecutorWorkStartedEvent,
    EventType.EXECUTOR_WORK_COMPLETED: ExecutorWorkCompletedEvent,
    EventType.EXECUTOR_WORK_FAILED: ExecutorWorkFailedEvent,
    EventType.EXECUTOR_WORK_CANCELLED: ExecutorWorkCancelledEvent,
    EventType.EXECUTOR_METRICS_UPDATED: ExecutorMetricsUpdatedEvent,
    EventType.EXECUTOR_SATURATION_CHANGED: ExecutorSaturationChangedEvent,
    EventType.EXECUTOR_CONTENTION_DETECTED: ExecutorContentionDetectedEvent,
    EventType.EXECUTOR_LATENCY_SPIKE_DETECTED: ExecutorLatencySpikeDetectedEvent,
    EventType.RUNTIME_STARTED: RuntimeStartedEvent,
    EventType.RUNTIME_STOPPED: RuntimeStoppedEvent,
    EventType.RUNTIME_WARNING: WarningEvent,
    EventType.RUNTIME_METRIC: MetricEvent,
}


def to_dict(event: RuntimeEvent) -> dict[str, Any]:
    """JSON-safe, websocket-safe serialization of an event."""
    return event.model_dump(mode="json")


def to_json(event: RuntimeEvent) -> str:
    return event.model_dump_json()


def from_dict(data: dict[str, Any]) -> RuntimeEvent:
    """Reconstruct the right :class:`RuntimeEvent` subclass from a dict.

    Falls back to :class:`GenericEvent` for unknown ``event_type`` values so
    the protocol stays forward-compatible: an old client receiving a new
    event type still gets a usable, routable object.
    """
    if not isinstance(data, dict):
        raise EventValidationError(f"expected mapping, got {type(data).__name__}")

    event_type = data.get("event_type")
    if not isinstance(event_type, str) or not event_type:
        raise EventValidationError("missing or empty event_type")

    cls = EVENT_REGISTRY.get(event_type, GenericEvent)
    try:
        return cls.model_validate(data)
    except Exception as exc:  # ValueError / pydantic.ValidationError
        raise EventValidationError(f"failed to validate {event_type!r}: {exc}") from exc
