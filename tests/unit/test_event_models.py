from __future__ import annotations

import json
import time
import uuid

import pytest

from asyncviz.runtime.events.models import (
    EVENT_REGISTRY,
    PROTOCOL_VERSION,
    EventSource,
    EventType,
    EventValidationError,
    GenericEvent,
    LoopBlockedEvent,
    MetricEvent,
    RuntimeEvent,
    RuntimeStartedEvent,
    RuntimeState,
    RuntimeStoppedEvent,
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
    TaskResumedEvent,
    TaskStartedEvent,
    TaskWaitingEvent,
    WarningEvent,
    WarningSeverity,
    create_loop_blocked,
    create_runtime_metric,
    create_runtime_started,
    create_runtime_stopped,
    create_runtime_warning,
    create_task_cancelled,
    create_task_completed,
    create_task_created,
    create_task_failed,
    from_dict,
    to_dict,
    to_json,
)

# ── base envelope ──────────────────────────────────────────────────────────


def test_protocol_version_is_one() -> None:
    assert PROTOCOL_VERSION == 1


def test_base_event_envelope_defaults() -> None:
    event = GenericEvent(event_type="custom")
    assert isinstance(event.event_id, uuid.UUID)
    assert event.event_type == "custom"
    assert event.timestamp > 0
    assert event.monotonic_timestamp > 0
    assert isinstance(event.runtime_id, uuid.UUID)
    assert event.source == EventSource.RUNTIME.value
    assert event.payload_version == 1


def test_base_event_is_frozen() -> None:
    event = GenericEvent(event_type="custom")
    with pytest.raises(Exception):  # noqa: B017 — Pydantic raises ValidationError
        event.event_type = "tampered"  # type: ignore[misc]


def test_runtime_event_of_returns_generic() -> None:
    event = RuntimeEvent.of("custom.thing", foo=1, bar="x")
    assert isinstance(event, GenericEvent)
    assert event.event_type == "custom.thing"
    assert event.payload == {"foo": 1, "bar": "x"}


# ── enum taxonomy ──────────────────────────────────────────────────────────


def test_event_type_enum_values_are_dotted() -> None:
    for member in EventType:
        assert "." in member.value, f"{member} should follow dotted convention"


def test_event_type_enum_matches_registered_classes() -> None:
    # Every registered event class must declare an event_type that matches a
    # member of the EventType enum (the canonical taxonomy).
    enum_values = {member.value for member in EventType}
    for type_value in EVENT_REGISTRY:
        assert type_value in enum_values


def test_enum_str_values() -> None:
    assert str(WarningSeverity.WARNING) == "warning"
    assert str(TaskCreatedEvent.model_fields["event_type"].default) == EventType.TASK_CREATED


# ── task events ────────────────────────────────────────────────────────────


def test_task_created_event_minimal() -> None:
    event = TaskCreatedEvent(task_id="t1")
    assert event.event_type == "asyncio.task.created"
    assert event.task_id == "t1"
    assert event.parent_task_id is None
    assert event.metadata == {}


def test_task_created_event_full() -> None:
    rid = uuid.uuid4()
    event = TaskCreatedEvent(
        task_id="t1",
        parent_task_id="t0",
        coroutine_name="my_coro",
        task_name="worker-1",
        runtime_id=rid,
        source=EventSource.INSTRUMENTATION.value,
        metadata={"queue": "io"},
    )
    assert event.task_name == "worker-1"
    assert event.runtime_id == rid
    assert event.source == "instrumentation"
    assert event.metadata == {"queue": "io"}


@pytest.mark.parametrize(
    "cls, expected_type",
    [
        (TaskCreatedEvent, EventType.TASK_CREATED),
        (TaskStartedEvent, EventType.TASK_STARTED),
        (TaskWaitingEvent, EventType.TASK_WAITING),
        (TaskResumedEvent, EventType.TASK_RESUMED),
        (TaskCompletedEvent, EventType.TASK_COMPLETED),
        (TaskCancelledEvent, EventType.TASK_CANCELLED),
        (TaskFailedEvent, EventType.TASK_FAILED),
    ],
)
def test_task_event_types_match_enum(cls, expected_type: str) -> None:
    event = cls(task_id="t1")
    assert event.event_type == expected_type


def test_task_completed_carries_duration() -> None:
    event = TaskCompletedEvent(task_id="t1", duration_seconds=1.5)
    assert event.duration_seconds == 1.5


def test_task_failed_carries_exception_info() -> None:
    event = TaskFailedEvent(task_id="t1", exception_type="RuntimeError", exception_message="boom")
    assert event.exception_type == "RuntimeError"
    assert event.exception_message == "boom"


# ── runtime / warning / metric events ──────────────────────────────────────


def test_runtime_started_event() -> None:
    event = RuntimeStartedEvent()
    assert event.event_type == EventType.RUNTIME_STARTED
    assert event.runtime_state == RuntimeState.RUNNING


def test_runtime_stopped_event() -> None:
    event = RuntimeStoppedEvent(uptime_seconds=3.5)
    assert event.event_type == EventType.RUNTIME_STOPPED
    assert event.runtime_state == RuntimeState.STOPPED
    assert event.uptime_seconds == 3.5


def test_loop_blocked_event_requires_blocked_seconds() -> None:
    event = LoopBlockedEvent(blocked_seconds=0.25, task_id="t1")
    assert event.blocked_seconds == 0.25
    assert event.task_id == "t1"


def test_warning_event_defaults_to_warning_severity() -> None:
    event = WarningEvent(message="hello")
    assert event.severity == WarningSeverity.WARNING
    assert event.message == "hello"


def test_metric_event_round_numbers() -> None:
    event = MetricEvent(name="loop.lag", value=12.5, unit="ms", tags={"host": "h1"})
    assert event.name == "loop.lag"
    assert event.value == 12.5
    assert event.unit == "ms"
    assert event.tags == {"host": "h1"}


# ── factories ──────────────────────────────────────────────────────────────


def test_factory_create_task_created() -> None:
    event = create_task_created(task_id="t1", coroutine_name="my_coro")
    assert isinstance(event, TaskCreatedEvent)
    assert event.task_id == "t1"
    assert event.coroutine_name == "my_coro"
    assert event.source == EventSource.INSTRUMENTATION.value


def test_factory_create_task_completed_uses_runtime_id() -> None:
    rid = uuid.uuid4()
    event = create_task_completed(task_id="t1", duration_seconds=0.5, runtime_id=rid)
    assert event.duration_seconds == 0.5
    assert event.runtime_id == rid


def test_factory_create_task_failed() -> None:
    event = create_task_failed(
        task_id="t1",
        exception_type="ValueError",
        exception_message="nope",
        duration_seconds=0.1,
    )
    assert event.exception_type == "ValueError"
    assert event.exception_message == "nope"


def test_factory_create_task_cancelled() -> None:
    event = create_task_cancelled(task_id="t1", duration_seconds=0.2)
    assert event.duration_seconds == 0.2


def test_factory_create_runtime_lifecycle_events() -> None:
    started = create_runtime_started()
    stopped = create_runtime_stopped(uptime_seconds=2.0)
    assert started.source == EventSource.LIFECYCLE.value
    assert stopped.uptime_seconds == 2.0


def test_factory_create_loop_blocked() -> None:
    event = create_loop_blocked(blocked_seconds=1.5, task_id="t1")
    assert event.blocked_seconds == 1.5
    assert event.task_id == "t1"


def test_factory_create_runtime_warning() -> None:
    event = create_runtime_warning(
        message="slow",
        severity=WarningSeverity.ERROR,
        category="loop.lag",
        metadata={"loop_id": 1},
    )
    assert event.severity == WarningSeverity.ERROR
    assert event.category == "loop.lag"
    assert event.metadata == {"loop_id": 1}


def test_factory_create_runtime_metric() -> None:
    event = create_runtime_metric(name="tasks", value=42, tags={"host": "h1"})
    assert event.name == "tasks"
    assert event.value == 42
    assert event.tags == {"host": "h1"}


# ── serialization ──────────────────────────────────────────────────────────


def test_to_dict_is_json_safe() -> None:
    event = create_task_created(task_id="t1", coroutine_name="my_coro")
    data = to_dict(event)
    # UUIDs and floats serialize cleanly; round-trip through json must work.
    serialized = json.dumps(data)
    reloaded = json.loads(serialized)
    assert reloaded["event_type"] == "asyncio.task.created"
    assert reloaded["task_id"] == "t1"
    assert reloaded["coroutine_name"] == "my_coro"


def test_to_json_is_str() -> None:
    event = create_runtime_warning(message="x")
    payload = json.loads(to_json(event))
    assert payload["event_type"] == "runtime.warning"
    assert payload["message"] == "x"


def test_from_dict_reconstructs_concrete_class() -> None:
    original = create_task_completed(task_id="t1", duration_seconds=0.5)
    raw = to_dict(original)
    rebuilt = from_dict(raw)
    assert isinstance(rebuilt, TaskCompletedEvent)
    assert rebuilt.task_id == "t1"
    assert rebuilt.duration_seconds == 0.5
    assert rebuilt.event_id == original.event_id


def test_from_dict_unknown_type_falls_back_to_generic() -> None:
    rebuilt = from_dict(
        {
            "event_type": "future.unknown.kind",
            "payload": {"x": 1},
            "timestamp": time.time(),
        }
    )
    assert isinstance(rebuilt, GenericEvent)
    assert rebuilt.event_type == "future.unknown.kind"
    assert rebuilt.payload == {"x": 1}


def test_from_dict_rejects_missing_event_type() -> None:
    with pytest.raises(EventValidationError):
        from_dict({"timestamp": 1.0})


def test_from_dict_rejects_non_mapping() -> None:
    with pytest.raises(EventValidationError):
        from_dict("not a dict")  # type: ignore[arg-type]


def test_from_dict_rejects_invalid_event_payload() -> None:
    # LoopBlockedEvent requires blocked_seconds; omitting it must fail.
    with pytest.raises(EventValidationError):
        from_dict({"event_type": "asyncio.loop.blocked"})


def test_round_trip_preserves_all_fields() -> None:
    rid = uuid.uuid4()
    original = TaskWaitingEvent(
        task_id="t1",
        parent_task_id="t0",
        coroutine_name="c",
        task_name="n",
        reason="lock",
        runtime_id=rid,
        source=EventSource.INSTRUMENTATION.value,
    )
    rebuilt = from_dict(to_dict(original))
    assert isinstance(rebuilt, TaskWaitingEvent)
    assert rebuilt.task_id == "t1"
    assert rebuilt.reason == "lock"
    assert rebuilt.runtime_id == rid


def test_payload_version_is_preserved_through_roundtrip() -> None:
    event = TaskCreatedEvent(task_id="t1", payload_version=7)
    rebuilt = from_dict(to_dict(event))
    assert rebuilt.payload_version == 7
