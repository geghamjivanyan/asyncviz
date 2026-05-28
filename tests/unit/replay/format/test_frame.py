"""Tests for the canonical replay frame envelope."""

from __future__ import annotations

import pytest

from asyncviz.replay.format import SCHEMA_VERSION, ReplayFrame


def test_runtime_event_factory_sets_envelope() -> None:
    frame = ReplayFrame.for_runtime_event(
        sequence=1,
        monotonic_ns=999,
        payload_type="asyncio.task.created",
        payload={"task_id": "t-1", "task_name": "n"},
        runtime_id="rt-1",
        recording_id="rec-1",
        wall_time_ns=42,
    )
    assert frame.schema_version == SCHEMA_VERSION
    assert frame.frame_type == "runtime_event"
    assert frame.payload_type == "asyncio.task.created"
    assert frame.sequence == 1
    assert frame.monotonic_ns == 999
    assert frame.runtime_id == "rt-1"
    assert frame.recording_id == "rec-1"
    assert frame.wall_time_ns == 42


def test_snapshot_factory_assigns_frame_type() -> None:
    begin = ReplayFrame.for_snapshot(
        kind="begin", sequence=1, monotonic_ns=1, payload={"snapshot_id": "s1"},
    )
    end = ReplayFrame.for_snapshot(
        kind="end", sequence=2, monotonic_ns=2, payload={"snapshot_id": "s1"},
    )
    delta = ReplayFrame.for_snapshot(
        kind="delta", sequence=3, monotonic_ns=3, payload={"snapshot_id": "s1"},
    )
    assert begin.frame_type == "snapshot_begin"
    assert end.frame_type == "snapshot_end"
    assert delta.frame_type == "snapshot_delta"


def test_to_dict_omits_unset_optionals() -> None:
    frame = ReplayFrame.for_runtime_event(
        sequence=1, monotonic_ns=1, payload_type="t", payload={"a": 1},
    )
    data = frame.to_dict()
    assert "runtime_id" not in data
    assert "recording_id" not in data
    assert "wall_time_ns" not in data
    assert "extensions" not in data


def test_from_dict_round_trip_preserves_envelope() -> None:
    frame = ReplayFrame.for_runtime_event(
        sequence=7,
        monotonic_ns=12345,
        payload_type="asyncio.task.completed",
        payload={"task_id": "t-7"},
        runtime_id="rt",
        recording_id="rec",
        wall_time_ns=999,
    )
    restored = ReplayFrame.from_dict(frame.to_dict())
    assert restored == frame


def test_from_dict_routes_unknown_keys_to_extensions() -> None:
    frame = ReplayFrame.from_dict({
        "schema_version": 1,
        "frame_type": "runtime_event",
        "sequence": 1,
        "monotonic_ns": 1,
        "payload_type": "asyncio.task.created",
        "payload": {"task_id": "t"},
        "future_field": "from-a-newer-producer",
        "another_thing": 42,
    })
    assert frame.extensions == {
        "future_field": "from-a-newer-producer",
        "another_thing": 42,
    }


def test_from_dict_explicit_extensions_merge_without_clobber() -> None:
    frame = ReplayFrame.from_dict({
        "schema_version": 1,
        "frame_type": "marker",
        "sequence": 1,
        "monotonic_ns": 1,
        "payload_type": "marker.checkpoint",
        "payload": {},
        "extensions": {"a": 1, "b": 2},
        "stray": "from-newer",
    })
    assert frame.extensions["stray"] == "from-newer"
    assert frame.extensions["a"] == 1
    assert frame.extensions["b"] == 2


def test_from_dict_rejects_missing_required_keys() -> None:
    with pytest.raises(ValueError, match="missing required keys"):
        ReplayFrame.from_dict({"schema_version": 1, "frame_type": "runtime_event"})


def test_for_marker_uses_marker_prefix() -> None:
    frame = ReplayFrame.for_marker(sequence=1, monotonic_ns=1, marker_name="cp")
    assert frame.payload_type == "marker.cp"
    assert frame.frame_type == "marker"
