"""Shared fixtures for replay-seek tests."""

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
    CheckpointRuntime,
    CursorRuntime,
    ReducerRegistry,
    ReplayClock,
    ReplayScheduler,
    ReplayStateStore,
)
from asyncviz.replay.runtime.seek import (
    ReplaySeekConfig,
    ReplaySeekCoordinator,
    clear_seek_trace,
    reset_seek_metrics,
    set_seek_trace_enabled,
)
from asyncviz.runtime.events.models import TaskCreatedEvent


@pytest.fixture(autouse=True)
def _reset_seek_globals() -> None:
    reset_seek_metrics()
    clear_seek_trace()
    set_seek_trace_enabled(False)


def _write_lines(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line if line.endswith("\n") else line + "\n")


@pytest.fixture
def seek_session(tmp_path: Path) -> Path:
    session_dir = tmp_path / "seek-rec"
    session_dir.mkdir()

    def build(start: int, stop: int):
        return [
            make_runtime_event_frame(
                sequence=i,
                monotonic_ns=i * 1_000_000,
                event=TaskCreatedEvent(task_id=f"t-{i}", task_name=f"n-{i}"),
            )
            for i in range(start, stop + 1)
        ]

    chunk1_path = session_dir / EVENTS_DIRNAME / chunk_filename(1)
    chunk2_path = session_dir / EVENTS_DIRNAME / chunk_filename(2)
    _write_lines(chunk1_path, (encode_frame(f) for f in build(1, 10)))
    _write_lines(chunk2_path, (encode_frame(f) for f in build(11, 20)))

    snap_path = session_dir / SNAPSHOTS_DIRNAME / "000001.json"
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_payload = {
        "last_sequence": 10,
        "last_monotonic_ns": 10_000_000,
        "frames_applied": 10,
        "domains": {"tasks": {f"t-{i}": True for i in range(1, 11)}},
        "notes": {"source": "test"},
    }
    snap_path.write_text(json.dumps(snap_payload), encoding="utf-8")

    chunks = (
        ChunkRecord(
            index=1,
            filename=chunk1_path.name,
            event_count=10,
            byte_size=chunk1_path.stat().st_size,
            first_sequence=1,
            last_sequence=10,
            sha256=compute_chunk_hash(chunk1_path),
        ),
        ChunkRecord(
            index=2,
            filename=chunk2_path.name,
            event_count=10,
            byte_size=chunk2_path.stat().st_size,
            first_sequence=11,
            last_sequence=20,
            sha256=compute_chunk_hash(chunk2_path),
        ),
    )
    snapshots = (
        SnapshotRecord(
            index=1,
            filename=snap_path.name,
            sequence_at_capture=10,
            kind="full",
            byte_size=snap_path.stat().st_size,
        ),
    )
    metadata = RecordingMetadata(
        schema_version=1,
        recording_id="seek-rec",
        runtime_id="rt-seek",
        asyncviz_version="0.1.0",
        started_at_ns=0,
        stopped_at_ns=20_000_000,
        chunks=chunks,
        snapshots=snapshots,
        event_count=20,
        chunk_count=2,
        snapshot_count=1,
        last_sequence=20,
        finalized=True,
    )
    write_manifest(session_dir, metadata)
    return session_dir


@pytest.fixture
def loader(seek_session: Path) -> ReplayEventLoader:
    return ReplayEventLoader.open(seek_session)


@pytest.fixture
def coordinator(loader: ReplayEventLoader) -> ReplaySeekCoordinator:
    clock = ReplayClock()
    scheduler = ReplayScheduler(clock)
    state = ReplayStateStore()
    cursor = CursorRuntime()
    checkpoints = CheckpointRuntime()
    reducers = ReducerRegistry()
    return ReplaySeekCoordinator(
        loader=loader,
        state_store=state,
        engine_cursor=cursor,
        clock=clock,
        scheduler=scheduler,
        checkpoints=checkpoints,
        reducers=reducers,
        config=ReplaySeekConfig(pause_before_seek=False),
    )
