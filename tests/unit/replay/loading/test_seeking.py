"""Seek operations: by sequence, by timestamp, snapshot-aware."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.loading import (
    ReplayEventLoader,
    get_loader_metrics_snapshot,
    iter_from_cursor,
    plan_sequence_seek,
)


def test_seek_to_existing_sequence_lands_on_target(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        result = loader.seek_to_sequence(7)
    assert result.landed_frame is not None
    assert result.landed_frame.sequence == 7
    assert result.cursor.last_sequence == 7
    assert result.cursor.chunk_index == 2


def test_seek_to_sequence_associates_nearest_snapshot(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        result = loader.seek_to_sequence(8)
    # snapshot was captured at seq=3, so cursor should reference it.
    assert result.cursor.snapshot_index == 1


def test_seek_beyond_recording_returns_no_match(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        result = loader.seek_to_sequence(99)
    assert result.landed_frame is None
    assert result.cursor.last_sequence == 0


def test_seek_to_timestamp_lands_on_first_frame_at_or_after(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        # frames carry monotonic_ns = sequence * 100, so target=650
        # should land on frame 7 (monotonic_ns=700).
        result = loader.seek_to_timestamp(650)
    assert result.landed_frame.sequence == 7
    assert result.landed_frame.monotonic_ns == 700


def test_seek_metric_counts_chunks_scanned(canonical_session: Path) -> None:
    before = get_loader_metrics_snapshot().seek_chunk_scans
    with ReplayEventLoader.open(canonical_session) as loader:
        loader.seek_to_sequence(8)
    after = get_loader_metrics_snapshot().seek_chunk_scans
    # Sequence 8 is in chunk 2 — we should only scan one chunk.
    assert after - before == 1


def test_plan_sequence_seek_uses_index_directly(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        plan = plan_sequence_seek(
            7,
            sequence_index=loader.sequence_index,
            snapshot_index=loader.snapshot_index,
            chunks=loader.session.chunks,
        )
    assert plan.starting_chunk_index == 2
    assert plan.snapshot is not None
    assert plan.snapshot.sequence_at_capture == 3


def test_iter_from_cursor_resumes_strictly_after(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        result = loader.seek_to_sequence(4)
        seqs = [
            f.sequence
            for f in iter_from_cursor(
                result.cursor,
                chunks=loader.session.chunks,
                chunk_paths=loader.session.chunk_paths,
                adapter=loader.adapter,
            )
        ]
    assert seqs == [5, 6, 7, 8, 9, 10]
