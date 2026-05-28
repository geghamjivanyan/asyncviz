"""Manifest loader + sequence/snapshot index tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from asyncviz.replay.loading import (
    ManifestLoadError,
    ReplayIndex,
    ReplaySnapshotIndex,
    load_manifest,
    load_manifest_or_rebuild,
)


def test_load_manifest_returns_full_session(canonical_session: Path) -> None:
    result = load_manifest(canonical_session)
    assert result.fully_resolved
    assert result.session.metadata.event_count == 10
    assert len(result.session.chunk_paths) == 2
    assert len(result.session.snapshot_paths) == 1


def test_load_manifest_reports_missing_chunks(canonical_session: Path) -> None:
    chunk_path = canonical_session / "events" / "000002.ndjson"
    chunk_path.unlink()
    result = load_manifest(canonical_session)
    assert not result.fully_resolved
    assert chunk_path in result.missing_chunk_paths


def test_load_manifest_raises_on_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(ManifestLoadError):
        load_manifest(tmp_path)


def test_load_manifest_or_rebuild_scans_chunks(tmp_path: Path) -> None:
    events_dir = tmp_path / "events"
    events_dir.mkdir()
    (events_dir / "000001.ndjson").write_text("", encoding="utf-8")
    (events_dir / "000002.ndjson").write_text("", encoding="utf-8")
    result = load_manifest_or_rebuild(tmp_path)
    assert result.session.metadata.chunk_count == 2
    assert len(result.session.chunk_paths) == 2


def test_replay_index_binary_search(canonical_session: Path) -> None:
    result = load_manifest(canonical_session)
    index = ReplayIndex.from_metadata(result.session.metadata)
    # chunk 1 covers seq 1..5, chunk 2 covers 6..10
    assert index.chunk_for_sequence(1).chunk_index == 1
    assert index.chunk_for_sequence(5).chunk_index == 1
    assert index.chunk_for_sequence(6).chunk_index == 2
    assert index.chunk_for_sequence(10).chunk_index == 2
    assert index.chunk_for_sequence(11) is None
    assert index.chunk_for_sequence(0) is None


def test_replay_index_from_session_dir(canonical_session: Path) -> None:
    result = load_manifest(canonical_session)
    index = ReplayIndex.from_session_dir(canonical_session, result.session.metadata)
    assert index.chunk_count == 2
    assert index.min_sequence == 1
    assert index.max_sequence == 10


def test_snapshot_index_nearest_at_or_before(canonical_session: Path) -> None:
    result = load_manifest(canonical_session)
    snap_index = ReplaySnapshotIndex.from_records(
        result.session.snapshots, result.session.snapshot_paths,
    )
    assert snap_index.snapshot_count == 1
    # snapshot captured at sequence 3
    assert snap_index.nearest_at_or_before(2) is None
    assert snap_index.nearest_at_or_before(3).sequence_at_capture == 3
    assert snap_index.nearest_at_or_before(100).sequence_at_capture == 3
