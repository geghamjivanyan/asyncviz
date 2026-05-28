"""Shared fixtures for replay-runtime engine tests."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pytest

from asyncviz.replay.format import encode_frame, make_runtime_event_frame
from asyncviz.replay.loading import ReplayEventLoader
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
from asyncviz.replay.runtime import (
    clear_engine_trace,
    reset_engine_metrics,
    set_engine_trace_enabled,
)
from asyncviz.runtime.events.models import TaskCreatedEvent


@pytest.fixture(autouse=True)
def _reset_engine_globals() -> None:
    reset_engine_metrics()
    clear_engine_trace()
    set_engine_trace_enabled(False)


def _write_lines(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line if line.endswith("\n") else line + "\n")


@pytest.fixture
def engine_session(tmp_path: Path) -> Path:
    """A small canonical-format recording with a mid-stream snapshot."""
    session_dir = tmp_path / "engine-rec"
    session_dir.mkdir()

    def build(start: int, stop: int):
        return [
            make_runtime_event_frame(
                sequence=i,
                monotonic_ns=i * 1_000_000,  # 1ms per frame
                event=TaskCreatedEvent(task_id=f"t-{i}", task_name=f"n-{i}"),
            )
            for i in range(start, stop + 1)
        ]

    chunk1_frames = build(1, 5)
    chunk2_frames = build(6, 10)
    chunk1_path = session_dir / EVENTS_DIRNAME / chunk_filename(1)
    chunk2_path = session_dir / EVENTS_DIRNAME / chunk_filename(2)
    _write_lines(chunk1_path, (encode_frame(f) for f in chunk1_frames))
    _write_lines(chunk2_path, (encode_frame(f) for f in chunk2_frames))

    # Snapshot captured at sequence 5 — payload encodes the
    # VirtualRuntimeState's dict form so the snapshot runtime can
    # restore it directly.
    snap_path = session_dir / SNAPSHOTS_DIRNAME / "000001.json"
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_payload = {
        "last_sequence": 5,
        "last_monotonic_ns": 5_000_000,
        "frames_applied": 5,
        "domains": {"tasks": {"t-1": True, "t-2": True, "t-3": True, "t-4": True, "t-5": True}},
        "notes": {"source": "test"},
    }
    snap_path.write_text(json.dumps(snap_payload), encoding="utf-8")

    chunks = (
        ChunkRecord(
            index=1, filename=chunk1_path.name,
            event_count=5, byte_size=chunk1_path.stat().st_size,
            first_sequence=1, last_sequence=5,
            sha256=compute_chunk_hash(chunk1_path),
        ),
        ChunkRecord(
            index=2, filename=chunk2_path.name,
            event_count=5, byte_size=chunk2_path.stat().st_size,
            first_sequence=6, last_sequence=10,
            sha256=compute_chunk_hash(chunk2_path),
        ),
    )
    snapshots = (
        SnapshotRecord(
            index=1, filename=snap_path.name,
            sequence_at_capture=5, kind="full",
            byte_size=snap_path.stat().st_size,
        ),
    )
    metadata = RecordingMetadata(
        schema_version=1,
        recording_id="engine-rec-1",
        runtime_id="rt-engine",
        asyncviz_version="0.1.0",
        started_at_ns=0,
        stopped_at_ns=10_000_000,
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
def loader(engine_session: Path) -> ReplayEventLoader:
    return ReplayEventLoader.open(engine_session)
