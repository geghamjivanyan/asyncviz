"""Snapshot/delta payload model round-trip tests."""

from __future__ import annotations

from asyncviz.replay.format import (
    ReplayFrame,
    decode_frame,
    encode_frame,
)
from asyncviz.replay.format.models import (
    MarkerPayload,
    RecordingMetadataPayload,
    SchemaMetadataPayload,
    SnapshotDeltaPayload,
    SnapshotEndPayload,
    SnapshotStartPayload,
)


def test_snapshot_start_payload_round_trip() -> None:
    payload = SnapshotStartPayload(
        snapshot_id="snap-1",
        captured_at_ns=100,
        sequence_at_capture=42,
        kind="full",
    )
    frame = ReplayFrame.for_snapshot(
        kind="begin",
        sequence=42,
        monotonic_ns=100,
        payload=payload.to_dict(),
    )
    restored = decode_frame(encode_frame(frame))
    assert SnapshotStartPayload.from_dict(restored.payload) == payload


def test_snapshot_end_payload_round_trip() -> None:
    payload = SnapshotEndPayload(snapshot_id="snap-1", byte_size=12345, delta_count=7)
    frame = ReplayFrame.for_snapshot(
        kind="end", sequence=43, monotonic_ns=200, payload=payload.to_dict(),
    )
    restored = decode_frame(encode_frame(frame))
    assert SnapshotEndPayload.from_dict(restored.payload) == payload


def test_snapshot_delta_payload_round_trip_with_value() -> None:
    payload = SnapshotDeltaPayload(
        snapshot_id="snap-1",
        selector="tasks.t-1.state",
        op="set",
        value="running",
    )
    frame = ReplayFrame.for_snapshot(
        kind="delta", sequence=44, monotonic_ns=300, payload=payload.to_dict(),
    )
    restored = decode_frame(encode_frame(frame))
    out = SnapshotDeltaPayload.from_dict(restored.payload)
    assert out == payload


def test_snapshot_delta_unset_op_drops_value() -> None:
    payload = SnapshotDeltaPayload(snapshot_id="s", selector="x", op="unset")
    encoded = payload.to_dict()
    assert "value" not in encoded


def test_marker_payload_round_trip() -> None:
    payload = MarkerPayload(name="checkpoint", labels=("ci", "perf"), annotation="hot path")
    frame = ReplayFrame.for_marker(
        sequence=1, monotonic_ns=10, marker_name="checkpoint", payload=payload.to_dict(),
    )
    restored = decode_frame(encode_frame(frame))
    assert MarkerPayload.from_dict(restored.payload) == payload


def test_recording_metadata_round_trip() -> None:
    payload = RecordingMetadataPayload(
        recording_id="rec-1",
        runtime_id="rt-1",
        asyncviz_version="0.1.0",
        started_at_ns=999,
        notes={"author": "test"},
    )
    frame = ReplayFrame.for_metadata(
        sequence=1,
        monotonic_ns=1,
        payload_type="metadata.recording",
        payload=payload.to_dict(),
    )
    restored = decode_frame(encode_frame(frame))
    assert RecordingMetadataPayload.from_dict(restored.payload) == payload


def test_schema_metadata_round_trip() -> None:
    payload = SchemaMetadataPayload(
        envelope_version=1,
        protocol_version=1,
        frame_types=("runtime_event", "snapshot_begin"),
        payload_types=("asyncio.task.created",),
    )
    frame = ReplayFrame.for_metadata(
        sequence=1,
        monotonic_ns=1,
        payload_type="metadata.schema",
        payload=payload.to_dict(),
    )
    restored = decode_frame(encode_frame(frame))
    assert SchemaMetadataPayload.from_dict(restored.payload) == payload
