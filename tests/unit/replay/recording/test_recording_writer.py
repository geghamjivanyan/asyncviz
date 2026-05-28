"""Append + flush + rotation behaviour for :class:`RecordingWriter`."""

from __future__ import annotations

import json
import time
from pathlib import Path

from asyncviz.replay.recording import (
    RecordingConfig,
    RecordingWriter,
    iter_chunk_lines,
)


def _make_payload(seq: int, kind: str = "asyncio.task.created") -> dict:
    return {
        "sequence": seq,
        "event_id": f"evt-{seq}",
        "event_type": kind,
        "monotonic_ns": seq * 1_000_000,
        "payload": {"task_id": f"t-{seq}"},
    }


def test_append_persists_in_sequence_order(recording_root: Path) -> None:
    cfg = RecordingConfig(
        root_dir=recording_root,
        buffer_capacity=64,
        flush_interval_seconds=0.05,
        snapshot_on_start=False,
        snapshot_on_stop=False,
    )
    session = recording_root / "test-session"
    session.mkdir()
    writer = RecordingWriter(session, config=cfg)
    writer.start()
    try:
        for i in range(1, 6):
            writer.enqueue(sequence=i, payload=_make_payload(i))
        # Wait for the background worker to drain.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if writer.queue_depth == 0:
                break
            time.sleep(0.01)
    finally:
        writer.stop()
    chunk = session / "events" / "000001.ndjson"
    assert chunk.exists()
    lines = list(iter_chunk_lines(chunk))
    assert len(lines) == 5
    sequences = [json.loads(line)["sequence"] for line in lines]
    assert sequences == [1, 2, 3, 4, 5]


def test_synchronous_flush_drains_and_returns_count(recording_root: Path) -> None:
    cfg = RecordingConfig(
        root_dir=recording_root,
        buffer_capacity=64,
        flush_interval_seconds=10.0,  # ensure worker doesn't beat us
        snapshot_on_start=False,
        snapshot_on_stop=False,
    )
    session = recording_root / "sync-flush"
    session.mkdir()
    writer = RecordingWriter(session, config=cfg)
    # Don't start the worker so manual flush is the only consumer.
    for i in range(1, 4):
        writer.enqueue(sequence=i, payload=_make_payload(i))
    result = writer.flush()
    assert result.events_persisted == 3
    assert result.bytes_written > 0
    writer.stop()


def test_rotation_after_event_count_threshold(recording_root: Path) -> None:
    cfg = RecordingConfig(
        root_dir=recording_root,
        buffer_capacity=64,
        flush_interval_seconds=0.05,
        max_chunk_events=3,
        max_chunk_bytes=0,
        snapshot_on_start=False,
        snapshot_on_stop=False,
    )
    session = recording_root / "rotate"
    session.mkdir()
    writer = RecordingWriter(session, config=cfg)
    # Don't start worker; drive flushes manually so rotation is observable.
    for i in range(1, 8):
        writer.enqueue(sequence=i, payload=_make_payload(i))
    writer.flush()
    writer.stop()
    chunks = sorted((session / "events").glob("*.ndjson"))
    assert len(chunks) >= 2
    # First chunk should have exactly 3 events.
    assert len(list(iter_chunk_lines(chunks[0]))) == 3


def test_rotation_after_byte_threshold(recording_root: Path) -> None:
    big_payload = "x" * 100
    cfg = RecordingConfig(
        root_dir=recording_root,
        buffer_capacity=64,
        flush_interval_seconds=0.05,
        max_chunk_events=0,
        max_chunk_bytes=200,
        snapshot_on_start=False,
        snapshot_on_stop=False,
    )
    session = recording_root / "rotate-bytes"
    session.mkdir()
    writer = RecordingWriter(session, config=cfg)
    for i in range(1, 8):
        writer.enqueue(sequence=i, payload={"sequence": i, "blob": big_payload})
    writer.flush()
    writer.stop()
    chunks = sorted((session / "events").glob("*.ndjson"))
    assert len(chunks) >= 2


def test_drop_newest_policy_when_buffer_full(recording_root: Path) -> None:
    cfg = RecordingConfig(
        root_dir=recording_root,
        buffer_capacity=2,
        drop_policy="drop-newest",
        flush_interval_seconds=10.0,
        snapshot_on_start=False,
        snapshot_on_stop=False,
    )
    session = recording_root / "drop"
    session.mkdir()
    writer = RecordingWriter(session, config=cfg)
    results = [
        writer.enqueue(sequence=i, payload=_make_payload(i)) for i in range(1, 5)
    ]
    accepted = sum(1 for r in results if r.action == "accepted")
    dropped = sum(1 for r in results if r.action == "dropped-newest")
    assert accepted == 2
    assert dropped == 2
    writer.flush()
    writer.stop()


def test_writer_records_chunks_completed(recording_root: Path) -> None:
    cfg = RecordingConfig(
        root_dir=recording_root,
        buffer_capacity=64,
        max_chunk_events=2,
        max_chunk_bytes=0,
        flush_interval_seconds=10.0,
        snapshot_on_start=False,
        snapshot_on_stop=False,
    )
    session = recording_root / "completed"
    session.mkdir()
    writer = RecordingWriter(session, config=cfg)
    for i in range(1, 6):
        writer.enqueue(sequence=i, payload=_make_payload(i))
    writer.flush()
    writer.stop()
    chunks = writer.chunks_completed
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.sha256 is not None
        assert chunk.event_count > 0
