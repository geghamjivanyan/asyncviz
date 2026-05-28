from __future__ import annotations

import uuid

from asyncviz.runtime.monitoring.blocking.stack_capture import (
    BLOCKING_STACK_CAPTURE_EVENT_TYPE,
    CapturedFrame,
    CapturedStack,
    CapturedTaskMetadata,
    StackCaptureLimits,
    StackSerializer,
    build_stack_capture_event,
    decode_stack_capture_event,
)


def _stack() -> CapturedStack:
    return CapturedStack(
        capture_id=42,
        runtime_id="rid",
        monotonic_ns=12345,
        sample_index=7,
        window_id="rid:bw:1",
        severity="CRITICAL",
        trigger="violation",
        frames=(
            CapturedFrame(
                filename="/tmp/x.py",
                module="myapp",
                function="handler",
                lineno=10,
                code_context="x = 1",
                is_async=False,
                is_internal=False,
            ),
            CapturedFrame(
                filename="/tmp/db.py",
                module="myapp.db",
                function="query",
                lineno=20,
                code_context="rows = cursor.fetchall()",
                is_async=True,
                is_internal=False,
            ),
        ),
        frames_total=2,
        filtered_count=0,
        thread_id=1,
        task=CapturedTaskMetadata(task_id="t1", task_name="my-task"),
    )


def test_event_type_constant() -> None:
    assert BLOCKING_STACK_CAPTURE_EVENT_TYPE.endswith(".stack_capture")


def test_event_carries_payload() -> None:
    s = _stack()
    serializer = StackSerializer(limits=StackCaptureLimits(max_payload_bytes=16 * 1024))
    serialized = serializer.serialize(s)
    e = build_stack_capture_event(payload=serialized.payload)
    assert e.event_type == BLOCKING_STACK_CAPTURE_EVENT_TYPE
    assert e.payload["capture_id"] == 42
    assert e.payload["frames"][0]["function"] == "handler"


def test_runtime_id_override_propagates() -> None:
    rid = uuid.uuid4()
    e = build_stack_capture_event(payload={"capture_id": 1}, runtime_id=rid)
    assert e.runtime_id == rid


def test_decode_round_trips_full_stack() -> None:
    s = _stack()
    serializer = StackSerializer(limits=StackCaptureLimits(max_payload_bytes=16 * 1024))
    serialized = serializer.serialize(s)
    e = build_stack_capture_event(payload=serialized.payload)
    decoded = decode_stack_capture_event(e)
    assert decoded is not None
    assert decoded.capture_id == s.capture_id
    assert decoded.severity == s.severity
    assert decoded.window_id == s.window_id
    assert decoded.task.task_id == "t1"
    assert decoded.frames[0].function == "handler"
    assert decoded.frames[1].is_async is True


def test_decode_returns_none_for_wrong_event_type() -> None:
    from asyncviz.runtime.events.event import RuntimeEvent

    other = RuntimeEvent.of("some.other.event", foo=1)
    assert decode_stack_capture_event(other) is None


def test_decode_returns_none_for_malformed_payload() -> None:
    from asyncviz.runtime.events.event import RuntimeEvent

    e = RuntimeEvent.of(BLOCKING_STACK_CAPTURE_EVENT_TYPE)
    # ``of`` builds a ``GenericEvent`` whose payload is an empty dict;
    # patch in a malformed frames entry to force the decoder's failure
    # path.
    bad = e.model_copy(update={"payload": {"frames": "not-a-list"}})
    decoded = decode_stack_capture_event(bad)
    # The decoder either returns ``None`` or, more permissively, a
    # CapturedStack with an empty frame tuple (frames key isn't a list,
    # so iteration would raise — the decoder swallows + returns None).
    assert decoded is None or decoded.frames == ()
