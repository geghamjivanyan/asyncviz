from __future__ import annotations

import json

from asyncviz.runtime.replay.frames import ReplayFrame
from asyncviz.runtime.replay.recorder.replay_serializer import serialize_frame


def _frame(sequence: int = 1) -> ReplayFrame:
    return ReplayFrame(
        sequence=sequence,
        event_id=f"evt-{sequence}",
        event_type="asyncio.task.created",
        monotonic_ns=sequence * 1_000,
        wall_seconds=float(sequence),
        runtime_id="rt-x",
        task_id="t-1",
        parent_task_id=None,
        payload={"foo": "bar", "n": sequence},
    )


def test_serialize_frame_emits_newline_terminated_ndjson() -> None:
    payload = serialize_frame(_frame())
    assert payload.endswith(b"\n")
    record = json.loads(payload)
    assert record["sequence"] == 1
    assert record["event_type"] == "asyncio.task.created"
    assert record["payload"] == {"foo": "bar", "n": 1}


def test_serialize_frame_is_deterministic_for_same_frame() -> None:
    a = serialize_frame(_frame(7))
    b = serialize_frame(_frame(7))
    assert a == b, "serialization must be byte-stable for deterministic replay"


def test_serialize_frame_sorts_keys() -> None:
    record = json.loads(serialize_frame(_frame()))
    assert list(record.keys()) == sorted(record.keys())
