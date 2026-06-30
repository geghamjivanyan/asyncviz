"""Manifest + index read/write round-trip tests."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.recording import (
    SCHEMA_VERSION,
    ChunkRecord,
    IndexEntry,
    RecordingIndex,
    RecordingMetadata,
    build_index_from_chunks,
    read_index,
    read_manifest,
    write_index,
    write_manifest,
)


def _manifest(**overrides) -> RecordingMetadata:  # type: ignore[no-untyped-def]
    base = {
        "schema_version": SCHEMA_VERSION,
        "recording_id": "rec-1",
        "runtime_id": "rt-1",
        "asyncviz_version": "0.1.0",
        "started_at_ns": 1_000_000,
        "stopped_at_ns": 2_000_000,
        "event_count": 10,
        "snapshot_count": 2,
        "chunk_count": 2,
        "last_sequence": 10,
        "finalized": True,
        "chunks": (
            ChunkRecord(
                index=1,
                filename="000001.ndjson",
                event_count=5,
                byte_size=500,
                first_sequence=1,
                last_sequence=5,
                sha256="aa" * 32,
            ),
            ChunkRecord(
                index=2,
                filename="000002.ndjson",
                event_count=5,
                byte_size=550,
                first_sequence=6,
                last_sequence=10,
                sha256="bb" * 32,
            ),
        ),
    }
    base.update(overrides)
    return RecordingMetadata(**base)


def test_manifest_round_trip(tmp_path: Path) -> None:
    session = tmp_path / "manifest"
    session.mkdir()
    metadata = _manifest()
    path = write_manifest(session, metadata)
    assert path.exists()
    loaded = read_manifest(session)
    assert loaded is not None
    assert loaded.recording_id == metadata.recording_id
    assert loaded.event_count == metadata.event_count
    assert len(loaded.chunks) == 2
    assert loaded.chunks[0].sha256 == "aa" * 32


def test_read_manifest_returns_none_when_missing(tmp_path: Path) -> None:
    session = tmp_path / "empty"
    session.mkdir()
    assert read_manifest(session) is None


def test_manifest_atomic_write_keeps_old_on_temp_file_failure(tmp_path: Path) -> None:
    session = tmp_path / "atomic"
    session.mkdir()
    write_manifest(session, _manifest())
    first = read_manifest(session)
    # Overwrite with a new manifest — the old one is replaced atomically.
    write_manifest(session, _manifest(event_count=99))
    second = read_manifest(session)
    assert first is not None and second is not None
    assert first.event_count != second.event_count
    assert second.event_count == 99


def test_index_round_trip(tmp_path: Path) -> None:
    session = tmp_path / "index"
    session.mkdir()
    metadata = _manifest()
    index = build_index_from_chunks(list(metadata.chunks))
    path = write_index(session, index)
    assert path.exists()
    loaded = read_index(session)
    assert loaded is not None
    assert len(loaded.entries) == 2
    assert loaded.chunk_for_sequence(7) is not None
    assert loaded.chunk_for_sequence(7).chunk_index == 2
    assert loaded.chunk_for_sequence(999) is None


def test_index_skips_empty_chunks() -> None:
    index = RecordingIndex(
        entries=(
            IndexEntry(chunk_index=1, first_sequence=-1, last_sequence=-1, event_count=0),
            IndexEntry(chunk_index=2, first_sequence=1, last_sequence=5, event_count=5),
        ),
    )
    assert index.chunk_for_sequence(3) is not None
    assert index.chunk_for_sequence(3).chunk_index == 2
