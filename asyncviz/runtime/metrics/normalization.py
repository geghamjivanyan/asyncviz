"""Event → aggregation-intent classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
    TaskResumedEvent,
    TaskStartedEvent,
    TaskWaitingEvent,
)


class MetricsIntent(StrEnum):
    """What aggregations a runtime event should update."""

    CREATE = "create"  # increment ``total``/``active``
    START = "start"  # state transitions inside active
    WAIT = "wait"  # state transitions inside active
    RESUME = "resume"  # state transitions inside active
    COMPLETE = "complete"  # decrement active, increment completed, record duration
    CANCEL = "cancel"  # decrement active, increment cancelled, record duration
    FAIL = "fail"  # decrement active, increment failed, record duration
    IGNORE = "ignore"


_INTENT_BY_TYPE: dict[type[RuntimeEvent], MetricsIntent] = {
    TaskCreatedEvent: MetricsIntent.CREATE,
    TaskStartedEvent: MetricsIntent.START,
    TaskWaitingEvent: MetricsIntent.WAIT,
    TaskResumedEvent: MetricsIntent.RESUME,
    TaskCompletedEvent: MetricsIntent.COMPLETE,
    TaskCancelledEvent: MetricsIntent.CANCEL,
    TaskFailedEvent: MetricsIntent.FAIL,
}


@dataclass(frozen=True, slots=True)
class NormalizedMetricsEvent:
    """One event normalized for aggregator dispatch."""

    event: RuntimeEvent
    intent: MetricsIntent
    sequence: int | None
    event_id: str
    coroutine_name: str | None
    task_id: str | None
    duration_seconds: float | None
    cancellation_origin: str | None


def normalize(event: RuntimeEvent, *, sequence: int | None) -> NormalizedMetricsEvent:
    intent = _INTENT_BY_TYPE.get(type(event), MetricsIntent.IGNORE)
    coroutine_name = getattr(event, "coroutine_name", None)
    task_id = getattr(event, "task_id", None)
    duration_seconds = getattr(event, "duration_seconds", None)
    cancellation_origin = getattr(event, "cancellation_origin", None)
    return NormalizedMetricsEvent(
        event=event,
        intent=intent,
        sequence=sequence,
        event_id=str(event.event_id),
        coroutine_name=coroutine_name if isinstance(coroutine_name, str) else None,
        task_id=task_id if isinstance(task_id, str) else None,
        duration_seconds=(duration_seconds if isinstance(duration_seconds, (int, float)) else None),
        cancellation_origin=(cancellation_origin if isinstance(cancellation_origin, str) else None),
    )


def is_terminal_intent(intent: MetricsIntent) -> bool:
    return intent in (MetricsIntent.COMPLETE, MetricsIntent.CANCEL, MetricsIntent.FAIL)
