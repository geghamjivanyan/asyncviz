"""Serialization + deserialization round-trip tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.format import (
    SCHEMA_VERSION,
    FrameDecodingError,
    ReplayFrame,
    build_frame,
    decode_frame,
    encode_frame,
    encode_frames,
    get_format_metrics_snapshot,
    make_runtime_event_frame,
)
from asyncviz.runtime.events.models import TaskCreatedEvent


def _frame() -> ReplayFrame:
    return ReplayFrame.for_runtime_event(
        sequence=1,
        monotonic_ns=100,
        payload_type="asyncio.task.created",
        payload={"task_id": "t-1", "task_name": "n"},
        runtime_id="rt",
        recording_id="rec",
        wall_time_ns=10,
    )


def test_encode_frame_is_one_line_with_terminator() -> None:
    line = encode_frame(_frame())
    assert line.endswith("\n")
    assert line.count("\n") == 1


def test_encode_frame_is_deterministic() -> None:
    assert encode_frame(_frame()) == encode_frame(_frame())


def test_round_trip_recovers_frame() -> None:
    frame = _frame()
    line = encode_frame(frame)
    decoded = decode_frame(line)
    assert decoded == frame


def test_round_trip_runtime_event() -> None:
    event = TaskCreatedEvent(task_id="t-1", task_name="hello")
    frame = make_runtime_event_frame(sequence=42, monotonic_ns=123, event=event)
    line = encode_frame(frame)
    restored = decode_frame(line)
    assert restored.sequence == 42
    assert restored.payload_type == "asyncio.task.created"
    assert restored.payload["task_id"] == "t-1"
    assert restored.schema_version == SCHEMA_VERSION


def test_build_frame_uses_registered_codec() -> None:
    event = TaskCreatedEvent(task_id="t-9", task_name="x")
    frame = build_frame(
        frame_type="runtime_event",
        sequence=1,
        monotonic_ns=1,
        payload_type="asyncio.task.created",
        payload=event,
    )
    # Encoded payload is JSON-safe dict, not a pydantic model.
    assert isinstance(frame.payload, dict)
    assert frame.payload["task_id"] == "t-9"


def test_encode_frames_yields_one_line_each() -> None:
    frames = [
        ReplayFrame.for_runtime_event(
            sequence=i,
            monotonic_ns=i,
            payload_type="asyncio.task.created",
            payload={"task_id": f"t-{i}"},
        )
        for i in range(1, 5)
    ]
    lines = list(encode_frames(frames))
    assert len(lines) == 4
    for line in lines:
        assert line.endswith("\n")


def test_decode_rejects_non_json() -> None:
    with pytest.raises(FrameDecodingError):
        decode_frame("this-is-not-json\n")


def test_decode_rejects_non_object_top_level() -> None:
    with pytest.raises(FrameDecodingError):
        decode_frame("[1,2,3]\n")


def test_decode_rejects_missing_schema_version() -> None:
    with pytest.raises(FrameDecodingError):
        decode_frame(
            '{"frame_type":"runtime_event","sequence":1,"monotonic_ns":1,"payload_type":"x","payload":{}}\n'
        )


def test_decode_increments_metrics() -> None:
    decode_frame(encode_frame(_frame()))
    snap = get_format_metrics_snapshot()
    assert snap.frames_encoded == 1
    assert snap.frames_decoded == 1
    assert snap.malformed_frames == 0


def test_canonical_encoding_is_byte_stable_across_field_order() -> None:
    frame = _frame()
    # Build same frame with payload dict in different insertion order.
    reordered = ReplayFrame(
        schema_version=frame.schema_version,
        frame_type=frame.frame_type,
        sequence=frame.sequence,
        monotonic_ns=frame.monotonic_ns,
        payload_type=frame.payload_type,
        payload={"task_name": "n", "task_id": "t-1"},
        runtime_id=frame.runtime_id,
        recording_id=frame.recording_id,
        wall_time_ns=frame.wall_time_ns,
    )
    assert encode_frame(frame) == encode_frame(reordered)
