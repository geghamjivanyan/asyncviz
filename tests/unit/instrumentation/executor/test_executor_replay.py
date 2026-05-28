"""Replay-safety: every executor event round-trips through the wire encoder."""

from __future__ import annotations

import pytest

from asyncviz.runtime.events.models.executor import (
    EXECUTOR_EVENT_TYPES,
    ExecutorRegisteredEvent,
    ExecutorWorkCancelledEvent,
    ExecutorWorkCompletedEvent,
    ExecutorWorkFailedEvent,
    ExecutorWorkStartedEvent,
    ExecutorWorkSubmittedEvent,
)
from asyncviz.runtime.events.models.serialization import from_dict, to_dict

_BASE = {
    "executor_id": "e-1",
    "executor_kind": "Thread",
    "snapshot": {"executor_id": "e-1", "executor_kind": "Thread"},
}

_WORK_BASE = {
    **_BASE,
    "work_item_id": "w-1",
    "submitting_task_id": "t-7",
    "callable_name": "do_thing",
}


@pytest.mark.parametrize(
    ("cls", "extra"),
    [
        (
            ExecutorRegisteredEvent,
            {"max_workers": 4, "thread_name_prefix": "p", "name": "pool"},
        ),
        (ExecutorWorkSubmittedEvent, {}),
        (
            ExecutorWorkStartedEvent,
            {
                "worker_thread_name": "Thread-1",
                "submission_latency_seconds": 0.01,
            },
        ),
        (
            ExecutorWorkCompletedEvent,
            {"worker_thread_name": "Thread-1", "duration_seconds": 0.05},
        ),
        (
            ExecutorWorkFailedEvent,
            {
                "worker_thread_name": "Thread-1",
                "duration_seconds": 0.02,
                "exception_type": "ValueError",
            },
        ),
        (ExecutorWorkCancelledEvent, {"duration_seconds": 0.1}),
    ],
)
def test_executor_event_round_trip(cls, extra) -> None:  # type: ignore[no-untyped-def]
    payload = {**_WORK_BASE} if cls is not ExecutorRegisteredEvent else {**_BASE}
    event = cls(**payload, **extra)
    body = to_dict(event)
    restored = from_dict(body)
    assert type(restored) is cls
    assert restored.model_dump() == event.model_dump()


def test_executor_event_types_enum_matches_event_classes() -> None:
    assert set(EXECUTOR_EVENT_TYPES) == {
        "asyncio.executor.registered",
        "asyncio.executor.work.submitted",
        "asyncio.executor.work.started",
        "asyncio.executor.work.completed",
        "asyncio.executor.work.failed",
        "asyncio.executor.work.cancelled",
    }
