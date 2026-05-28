"""Integrity verification + corruption isolation tests."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.loading import (
    ReplayEventLoader,
    ReplayLoaderConfig,
    get_loader_metrics_snapshot,
    inspect_chunk,
    verify_session,
)


def test_verify_session_passes_for_clean_recording(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        report = verify_session(loader.session.chunks, loader.session.chunk_paths)
    assert report.all_verified
    assert all(v.verified for v in report.verdicts)


def test_verify_session_detects_mutated_chunk(canonical_session: Path) -> None:
    # Append garbage to chunk 1, which changes its hash.
    chunk_path = canonical_session / "events" / "000001.ndjson"
    with chunk_path.open("a", encoding="utf-8") as fh:
        fh.write("garbage\n")
    with ReplayEventLoader.open(canonical_session) as loader:
        report = verify_session(loader.session.chunks, loader.session.chunk_paths)
    assert not report.all_verified
    assert any(v.chunk_index == 1 and not v.verified for v in report.verdicts)


def test_inspect_chunk_flags_missing_trailing_newline(canonical_session: Path) -> None:
    chunk_path = canonical_session / "events" / "000001.ndjson"
    # Strip trailing newline.
    raw = chunk_path.read_bytes()
    chunk_path.write_bytes(raw.rstrip(b"\n"))
    with ReplayEventLoader.open(canonical_session) as loader:
        healths = loader.chunk_health()
    chunk1 = next(h for h in healths if h.chunk_index == 1)
    assert not chunk1.has_trailing_newline
    assert not chunk1.healthy


def test_loader_isolates_malformed_lines_during_iteration(canonical_session: Path) -> None:
    chunk_path = canonical_session / "events" / "000001.ndjson"
    raw = chunk_path.read_text(encoding="utf-8")
    # Splice in a malformed line.
    halves = raw.split("\n", 2)
    spliced = halves[0] + "\n" + halves[1] + "\nNOT-VALID-JSON\n" + halves[2]
    chunk_path.write_text(spliced, encoding="utf-8")
    before = get_loader_metrics_snapshot().malformed_frames
    with ReplayEventLoader.open(canonical_session) as loader:
        seqs = [f.sequence for f in loader.iter_frames()]
    after = get_loader_metrics_snapshot().malformed_frames
    # The 5 valid frames in chunk 1 + all 5 in chunk 2 survive.
    assert seqs == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert after - before >= 1


def test_loader_verify_integrity_flag_runs_check(canonical_session: Path) -> None:
    cfg = ReplayLoaderConfig(session_dir=canonical_session, verify_integrity=True)
    with ReplayEventLoader.open(canonical_session, config=cfg) as loader:
        assert loader.integrity is not None
        assert loader.integrity.all_verified


def test_loader_handles_missing_chunk_gracefully(canonical_session: Path) -> None:
    chunk_path = canonical_session / "events" / "000002.ndjson"
    chunk_path.unlink()
    with ReplayEventLoader.open(canonical_session) as loader:
        seqs = [f.sequence for f in loader.iter_frames()]
    # Chunk 2 is missing — chunk 1 still yields its 5 frames.
    assert seqs == [1, 2, 3, 4, 5]


def test_inspect_chunk_module_function(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        chunk = loader.session.chunks[0]
        path = loader.session.chunk_paths[0]
        health = inspect_chunk(chunk, path)
    assert health.healthy
    assert health.line_count == 5
