"""End-to-end loader iteration tests."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.loading import (
    ReplayEventLoader,
    ReplayLoaderConfig,
    ReplayWindow,
    by_event_type,
    by_sequence_range,
    get_loader_metrics_snapshot,
)


def test_iter_frames_yields_in_sequence_order(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        seqs = [f.sequence for f in loader.iter_frames()]
    assert seqs == list(range(1, 11))


def test_iter_frames_advances_cursor(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        last_seq = 0
        for frame in loader.iter_frames():
            assert frame.sequence > last_seq
            last_seq = frame.sequence
            assert loader.cursor.last_sequence == frame.sequence


def test_iter_frames_respects_window_upper_bound(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        seqs = [f.sequence for f in loader.iter_frames(window=ReplayWindow.for_sequences(3, 6))]
    assert seqs == [3, 4, 5, 6]


def test_iter_frames_stops_on_above_window_early(canonical_session: Path) -> None:
    """The stream should not pay to walk chunks beyond the window."""
    with ReplayEventLoader.open(canonical_session) as loader:
        before = get_loader_metrics_snapshot().chunks_scanned
        for _ in loader.iter_frames(window=ReplayWindow.for_sequences(0, 4)):
            pass
        after = get_loader_metrics_snapshot().chunks_scanned
    # Only chunk 1 (seqs 1..5) should have been opened.
    assert after - before == 1


def test_iter_frames_with_filter_drops_non_matching(canonical_session: Path) -> None:
    flt = by_event_type("nonexistent")
    with ReplayEventLoader.open(canonical_session) as loader:
        seqs = [f.sequence for f in loader.iter_frames(frame_filter=flt)]
    assert seqs == []


def test_iter_frames_with_combined_filter(canonical_session: Path) -> None:
    flt = by_sequence_range(3, 7)
    with ReplayEventLoader.open(canonical_session) as loader:
        seqs = [f.sequence for f in loader.iter_frames(frame_filter=flt)]
    assert seqs == [3, 4, 5, 6, 7]


def test_iter_frames_can_resume_from_cursor(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        # First pass: take 4 frames.
        gen = loader.iter_frames()
        taken = []
        for frame in gen:
            taken.append(frame.sequence)
            if len(taken) == 4:
                break
        # Cursor must reflect the last yielded sequence (=4).
        assert loader.cursor.last_sequence == 4
        # Resume from the cursor — should yield 5..10.
        seqs = [f.sequence for f in loader.iter_frames(from_cursor=loader.cursor)]
    assert taken == [1, 2, 3, 4]
    assert seqs == [5, 6, 7, 8, 9, 10]


def test_open_with_config_uses_strict_mode(canonical_session: Path) -> None:
    cfg = ReplayLoaderConfig(session_dir=canonical_session, strict_mode=True)
    with ReplayEventLoader.open(canonical_session, config=cfg) as loader:
        # Just iterating a clean session shouldn't raise.
        assert sum(1 for _ in loader.iter_frames()) == 10


def test_loader_summary_reports_format(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        summary = loader.summary()
    assert summary.detected_format == "canonical"
    assert summary.event_count == 10


def test_loader_works_on_legacy_session(legacy_session: Path) -> None:
    with ReplayEventLoader.open(legacy_session) as loader:
        seqs = [f.sequence for f in loader.iter_frames()]
    assert seqs == [1, 2, 3, 4, 5]
    assert loader.summary().detected_format == "legacy_recording"
