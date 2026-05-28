"""Shared fixtures for replay-loader tests."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pytest

from asyncviz.replay.format import encode_frame, make_runtime_event_frame
from asyncviz.replay.loading import (
    clear_replay_trace,
    reset_loader_metrics,
    set_replay_trace_enabled,
)
from asyncviz.replay.recording.recording_integrity import compute_chunk_hash
from asyncviz.replay.recording.recording_layout import (
    EVENTS_DIRNAME,
    SNAPSHOTS_DIRNAME,
    chunk_filename,
)
from asyncviz.replay.recording.recording_manifest import write_manifest
from asyncviz.replay.recording.recording_metadata import (
    ChunkRecord,
    RecordingMetadata,
    SnapshotRecord,
)
from asyncviz.runtime.events.models import TaskCreatedEvent


@pytest.fixture(autouse=True)
def _reset_loader_globals() -> None:
    reset_loader_metrics()
    clear_replay_trace()
    set_replay_trace_enabled(False)


def _write_chunk_lines(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line if line.endswith("\n") else line + "\n")


@pytest.fixture
def canonical_session(tmp_path: Path):
    """Build a small canonical-format recording session on disk.

    Layout:
      session_dir/
        manifest.json
        events/000001.ndjson (sequences 1..5)
        events/000002.ndjson (sequences 6..10)
        snapshots/000001.json (sequence_at_capture=3)
    """
    session_dir = tmp_path / "rec"
    session_dir.mkdir()

    def build_frames(start: int, stop: int):
        return [
            make_runtime_event_frame(
                sequence=i,
                monotonic_ns=i * 100,
                event=TaskCreatedEvent(task_id=f"t-{i}", task_name=f"n-{i}"),
            )
            for i in range(start, stop + 1)
        ]

    chunk1_frames = build_frames(1, 5)
    chunk2_frames = build_frames(6, 10)
    chunk1_path = session_dir / EVENTS_DIRNAME / chunk_filename(1)
    chunk2_path = session_dir / EVENTS_DIRNAME / chunk_filename(2)
    _write_chunk_lines(chunk1_path, (encode_frame(f) for f in chunk1_frames))
    _write_chunk_lines(chunk2_path, (encode_frame(f) for f in chunk2_frames))

    snap_path = session_dir / SNAPSHOTS_DIRNAME / "000001.json"
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_payload = {"tasks": ["t-1", "t-2", "t-3"], "tick": 3}
    snap_path.write_text(json.dumps(snap_payload), encoding="utf-8")

    chunks = (
        ChunkRecord(
            index=1,
            filename=chunk1_path.name,
            event_count=5,
            byte_size=chunk1_path.stat().st_size,
            first_sequence=1,
            last_sequence=5,
            sha256=compute_chunk_hash(chunk1_path),
        ),
        ChunkRecord(
            index=2,
            filename=chunk2_path.name,
            event_count=5,
            byte_size=chunk2_path.stat().st_size,
            first_sequence=6,
            last_sequence=10,
            sha256=compute_chunk_hash(chunk2_path),
        ),
    )
    snapshots = (
        SnapshotRecord(
            index=1,
            filename=snap_path.name,
            sequence_at_capture=3,
            kind="full",
            byte_size=snap_path.stat().st_size,
        ),
    )
    metadata = RecordingMetadata(
        schema_version=1,
        recording_id="rec-1",
        runtime_id="rt-1",
        asyncviz_version="0.1.0",
        started_at_ns=1_000_000,
        stopped_at_ns=2_000_000,
        chunks=chunks,
        snapshots=snapshots,
        event_count=10,
        chunk_count=2,
        snapshot_count=1,
        last_sequence=10,
        finalized=True,
    )
    write_manifest(session_dir, metadata)
    return session_dir


@pytest.fixture
def legacy_session(tmp_path: Path):
    """Build a recording session using the legacy recorder format."""
    session_dir = tmp_path / "legacy"
    session_dir.mkdir()
    chunk_path = session_dir / EVENTS_DIRNAME / chunk_filename(1)
    lines = []
    for i in range(1, 6):
        lines.append(
            json.dumps(
                {
                    "sequence": i,
                    "event_id": f"id-{i}",
                    "event_type": "asyncio.task.created",
                    "monotonic_ns": i * 10,
                    "payload": {"task_id": f"t-{i}", "task_name": f"n-{i}"},
                },
                separators=(",", ":"),
            ),
        )
    _write_chunk_lines(chunk_path, lines)
    chunks = (
        ChunkRecord(
            index=1,
            filename=chunk_path.name,
            event_count=5,
            byte_size=chunk_path.stat().st_size,
            first_sequence=1,
            last_sequence=5,
            sha256=compute_chunk_hash(chunk_path),
        ),
    )
    metadata = RecordingMetadata(
        schema_version=1,
        recording_id="legacy-1",
        runtime_id="rt-legacy",
        asyncviz_version="0.0.9",
        started_at_ns=0,
        stopped_at_ns=0,
        chunks=chunks,
        snapshots=(),
        event_count=5,
        chunk_count=1,
        snapshot_count=0,
        last_sequence=5,
        finalized=True,
    )
    write_manifest(session_dir, metadata)
    return session_dir
