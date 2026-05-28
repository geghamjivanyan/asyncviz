"""Replay-safety: every gather event round-trips through the wire encoder."""

from __future__ import annotations

import pytest

from asyncviz.runtime.events.models.gather import (
    GATHER_EVENT_TYPES,
    GatherCancelledEvent,
    GatherChildAttachedEvent,
    GatherChildCompletedEvent,
    GatherCompletedEvent,
    GatherCreatedEvent,
    GatherFailedEvent,
    GatherWaitStartedEvent,
)
from asyncviz.runtime.events.models.serialization import from_dict, to_dict


@pytest.mark.parametrize(
    ("cls", "extra"),
    [
        (
            GatherCreatedEvent,
            {"child_task_ids": ("c1", "c2"), "return_exceptions": True},
        ),
        (GatherChildAttachedEvent, {"child_task_id": "c1", "child_index": 0}),
        (GatherWaitStartedEvent, {}),
        (
            GatherChildCompletedEvent,
            {
                "child_task_id": "c1",
                "child_index": 0,
                "cancelled": False,
                "failed": True,
                "completed_count": 1,
            },
        ),
        (
            GatherCompletedEvent,
            {
                "completed_count": 2,
                "cancelled_children": 0,
                "failed_children": 0,
                "duration_seconds": 0.42,
            },
        ),
        (
            GatherCancelledEvent,
            {"completed_count": 1, "duration_seconds": 0.1},
        ),
        (
            GatherFailedEvent,
            {
                "completed_count": 1,
                "duration_seconds": 0.2,
                "exception_type": "ValueError",
            },
        ),
    ],
)
def test_gather_event_round_trip(cls, extra) -> None:  # type: ignore[no-untyped-def]
    event = cls(
        gather_id="g-1",
        parent_task_id="t-7",
        child_count=2,
        snapshot={
            "gather_id": "g-1",
            "parent_task_id": "t-7",
            "child_count": 2,
            "completed_count": 0,
            "pending_count": 2,
            "cancelled": False,
            "failed": False,
            "return_exceptions": False,
        },
        **extra,
    )
    payload = to_dict(event)
    restored = from_dict(payload)
    assert type(restored) is cls
    assert restored.model_dump() == event.model_dump()


def test_gather_event_types_enum_matches_event_classes() -> None:
    assert set(GATHER_EVENT_TYPES) == {
        "asyncio.gather.created",
        "asyncio.gather.child.attached",
        "asyncio.gather.wait.started",
        "asyncio.gather.child.completed",
        "asyncio.gather.completed",
        "asyncio.gather.cancelled",
        "asyncio.gather.failed",
    }
