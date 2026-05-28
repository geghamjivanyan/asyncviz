"""Deterministic synthetic recordings on disk.

Returns a (session_dir, RecordingMetadata) pair built from a fixed
sequence of canonical replay frames. Used by replay benchmarks to
exercise loader / engine / seek paths without depending on an
existing recording fixture.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from asyncviz.replay.format import encode_frame, make_runtime_event_frame
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


def _write_lines(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line if line.endswith("\n") else line + "\n")


def build_synthetic_recording(
    session_dir: Path,
    *,
    frames_per_chunk: int = 50,
    chunks: int = 4,
    snapshot_every: int = 100,
) -> RecordingMetadata:
    """Build a deterministic recording on disk + return the manifest."""
    session_dir.mkdir(parents=True, exist_ok=True)

    chunk_records: list[ChunkRecord] = []
    snapshot_records: list[SnapshotRecord] = []
    next_sequence = 1
    next_snapshot_index = 1

    for chunk_index in range(1, chunks + 1):
        start = next_sequence
        stop = start + frames_per_chunk - 1
        frames = [
            make_runtime_event_frame(
                sequence=i,
                monotonic_ns=i * 1_000,
                event=TaskCreatedEvent(task_id=f"t-{i}", task_name=f"n-{i}"),
            )
            for i in range(start, stop + 1)
        ]
        chunk_path = session_dir / EVENTS_DIRNAME / chunk_filename(chunk_index)
        _write_lines(chunk_path, (encode_frame(f) for f in frames))
        chunk_records.append(
            ChunkRecord(
                index=chunk_index,
                filename=chunk_path.name,
                event_count=len(frames),
                byte_size=chunk_path.stat().st_size,
                first_sequence=start,
                last_sequence=stop,
                sha256=compute_chunk_hash(chunk_path),
            ),
        )
        # Snapshot at chunk boundary if requested.
        if snapshot_every > 0 and stop % snapshot_every == 0:
            snap_path = (
                session_dir
                / SNAPSHOTS_DIRNAME
                / chunk_filename(next_snapshot_index, extension="json")
            )
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "last_sequence": stop,
                "last_monotonic_ns": stop * 1_000,
                "frames_applied": stop,
                "domains": {"tasks": {f"t-{i}": True for i in range(start, stop + 1)}},
                "notes": {"source": "synthetic"},
            }
            snap_path.write_text(json.dumps(payload), encoding="utf-8")
            snapshot_records.append(
                SnapshotRecord(
                    index=next_snapshot_index,
                    filename=snap_path.name,
                    sequence_at_capture=stop,
                    kind="full",
                    byte_size=snap_path.stat().st_size,
                ),
            )
            next_snapshot_index += 1
        next_sequence = stop + 1

    metadata = RecordingMetadata(
        schema_version=1,
        recording_id=session_dir.name,
        runtime_id="bench-runtime",
        asyncviz_version="0.1.0",
        started_at_ns=0,
        stopped_at_ns=next_sequence * 1_000,
        chunks=tuple(chunk_records),
        snapshots=tuple(snapshot_records),
        event_count=sum(c.event_count for c in chunk_records),
        chunk_count=len(chunk_records),
        snapshot_count=len(snapshot_records),
        last_sequence=next_sequence - 1,
        finalized=True,
    )
    write_manifest(session_dir, metadata)
    return metadata
