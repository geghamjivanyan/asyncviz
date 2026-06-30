"""Frame adapter tests."""

from __future__ import annotations

import json

import pytest

from asyncviz.replay.format import encode_frame, make_runtime_event_frame
from asyncviz.replay.loading import (
    AutoDetectFrameAdapter,
    CanonicalFrameAdapter,
    FrameAdapterError,
    LegacyRecordingFrameAdapter,
    select_frame_adapter,
)
from asyncviz.runtime.events.models import TaskCreatedEvent


def _canonical_line() -> str:
    return encode_frame(
        make_runtime_event_frame(
            sequence=1,
            monotonic_ns=10,
            event=TaskCreatedEvent(task_id="t-1", task_name="n"),
        ),
    )


def _legacy_line() -> str:
    return (
        json.dumps(
            {
                "sequence": 1,
                "event_id": "id-1",
                "event_type": "asyncio.task.created",
                "monotonic_ns": 10,
                "payload": {"task_id": "t-1", "task_name": "n"},
            },
        )
        + "\n"
    )


def test_canonical_adapter_decodes_canonical_lines() -> None:
    adapter = CanonicalFrameAdapter()
    frame = adapter.decode_line(_canonical_line())
    assert frame.sequence == 1
    assert frame.payload_type == "asyncio.task.created"


def test_legacy_adapter_decodes_legacy_lines() -> None:
    adapter = LegacyRecordingFrameAdapter()
    frame = adapter.decode_line(_legacy_line())
    assert frame.sequence == 1
    assert frame.payload_type == "asyncio.task.created"
    assert frame.payload["task_id"] == "t-1"


def test_legacy_adapter_rejects_missing_keys() -> None:
    adapter = LegacyRecordingFrameAdapter()
    with pytest.raises(FrameAdapterError):
        adapter.decode_line('{"sequence":1}\n')


def test_auto_detect_picks_canonical_on_first_canonical_line() -> None:
    adapter = AutoDetectFrameAdapter()
    adapter.decode_line(_canonical_line())
    assert isinstance(adapter.selected, CanonicalFrameAdapter)


def test_auto_detect_picks_legacy_on_first_legacy_line() -> None:
    adapter = AutoDetectFrameAdapter()
    adapter.decode_line(_legacy_line())
    assert isinstance(adapter.selected, LegacyRecordingFrameAdapter)


def test_auto_detect_commits_after_first_decision() -> None:
    adapter = AutoDetectFrameAdapter()
    adapter.decode_line(_canonical_line())
    # Even feeding a legacy line afterward, the adapter should
    # apply the canonical decoder (which will raise).
    with pytest.raises(FrameAdapterError):
        adapter.decode_line(_legacy_line())


def test_select_frame_adapter_routes_format_strings() -> None:
    assert isinstance(select_frame_adapter("canonical"), CanonicalFrameAdapter)
    assert isinstance(select_frame_adapter("legacy_recording"), LegacyRecordingFrameAdapter)
    assert isinstance(select_frame_adapter("auto"), AutoDetectFrameAdapter)
