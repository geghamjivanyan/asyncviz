"""Replay-safety: every queue event round-trips through the wire encoder."""

from __future__ import annotations

import pytest

from asyncviz.runtime.events.models.queue import (
    QUEUE_EVENT_TYPES,
    QueueCancelledEvent,
    QueueCreatedEvent,
    QueueEmptyWaitEvent,
    QueueFullWaitEvent,
    QueueGetEvent,
    QueuePutEvent,
    QueueTaskDoneEvent,
)
from asyncviz.runtime.events.models.serialization import from_dict, to_dict


@pytest.mark.parametrize(
    ("cls", "extra"),
    [
        (QueueCreatedEvent, {"creator_task_id": "t-1", "name": "orders"}),
        (QueuePutEvent, {"nowait": True, "blocked": False, "wait_seconds": None}),
        (QueueGetEvent, {"nowait": False, "blocked": True, "wait_seconds": 0.4}),
        (QueueFullWaitEvent, {}),
        (QueueEmptyWaitEvent, {}),
        (QueueTaskDoneEvent, {}),
        (QueueCancelledEvent, {"operation": "put", "wait_seconds": 0.1}),
    ],
)
def test_queue_event_round_trip(cls, extra) -> None:  # type: ignore[no-untyped-def]
    event = cls(
        queue_id="q-1",
        queue_kind="Queue",
        maxsize=4,
        task_id="t-42",
        snapshot={
            "size": 0,
            "maxsize": 4,
            "blocked_putters": 0,
            "blocked_getters": 0,
            "unfinished_tasks": 0,
        },
        **extra,
    )
    payload = to_dict(event)
    restored = from_dict(payload)
    assert type(restored) is cls
    assert restored.model_dump() == event.model_dump()


def test_queue_event_types_enum_matches_event_classes() -> None:
    # If a new event class is added, this guard reminds us to update the
    # canonical list + the EventType enum + serializer registry together.
    assert set(QUEUE_EVENT_TYPES) == {
        "asyncio.queue.created",
        "asyncio.queue.put",
        "asyncio.queue.get",
        "asyncio.queue.full_wait",
        "asyncio.queue.empty_wait",
        "asyncio.queue.task_done",
        "asyncio.queue.cancelled",
    }
