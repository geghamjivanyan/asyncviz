"""Replay-safety: every semaphore event round-trips through the wire encoder."""

from __future__ import annotations

import pytest

from asyncviz.runtime.events.models.semaphore import (
    SEMAPHORE_EVENT_TYPES,
    SemaphoreAcquiredEvent,
    SemaphoreAcquireStartedEvent,
    SemaphoreContentionDetectedEvent,
    SemaphoreCreatedEvent,
    SemaphoreReleasedEvent,
    SemaphoreWaitCancelledEvent,
)
from asyncviz.runtime.events.models.serialization import from_dict, to_dict


@pytest.mark.parametrize(
    ("cls", "extra"),
    [
        (SemaphoreCreatedEvent, {"creator_task_id": "t-1", "name": "limiter"}),
        (SemaphoreAcquireStartedEvent, {"will_block": True}),
        (SemaphoreAcquiredEvent, {"blocked": True, "wait_seconds": 0.42}),
        (SemaphoreReleasedEvent, {}),
        (SemaphoreContentionDetectedEvent, {"waiter_count": 3, "current_value": 0}),
        (SemaphoreWaitCancelledEvent, {"wait_seconds": 0.1}),
    ],
)
def test_semaphore_event_round_trip(cls, extra) -> None:  # type: ignore[no-untyped-def]
    event = cls(
        semaphore_id="s-1",
        semaphore_kind="Semaphore",
        initial_value=4,
        bound_value=None,
        task_id="t-42",
        snapshot={
            "current_value": 2,
            "waiter_count": 0,
            "initial_value": 4,
            "bound_value": None,
        },
        **extra,
    )
    payload = to_dict(event)
    restored = from_dict(payload)
    assert type(restored) is cls
    assert restored.model_dump() == event.model_dump()


def test_semaphore_event_types_enum_matches_event_classes() -> None:
    assert set(SEMAPHORE_EVENT_TYPES) == {
        "asyncio.semaphore.created",
        "asyncio.semaphore.acquire.started",
        "asyncio.semaphore.acquired",
        "asyncio.semaphore.released",
        "asyncio.semaphore.contention.detected",
        "asyncio.semaphore.wait.cancelled",
    }
