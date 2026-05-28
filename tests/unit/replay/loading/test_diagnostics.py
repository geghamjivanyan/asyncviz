"""Diagnostics + tracing tests."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.loading import (
    ReplayEventLoader,
    build_loader_diagnostics,
    get_loader_metrics_snapshot,
    get_replay_trace,
    is_replay_trace_enabled,
    set_replay_trace_enabled,
)


def test_diagnostics_reflects_metrics_after_iteration(canonical_session: Path) -> None:
    with ReplayEventLoader.open(canonical_session) as loader:
        list(loader.iter_frames())
    diag = build_loader_diagnostics()
    assert diag.metrics.frames_loaded >= 10
    assert diag.metrics.chunks_scanned >= 2
    assert diag.metrics.sessions_opened >= 1
    assert diag.metrics.sessions_closed >= 1


def test_tracing_disabled_by_default(canonical_session: Path) -> None:
    assert not is_replay_trace_enabled()
    with ReplayEventLoader.open(canonical_session) as loader:
        list(loader.iter_frames())
    assert get_replay_trace() == ()


def test_tracing_captures_session_lifecycle(canonical_session: Path) -> None:
    set_replay_trace_enabled(True)
    try:
        with ReplayEventLoader.open(canonical_session) as loader:
            loader.seek_to_sequence(7)
        kinds = {e.kind for e in get_replay_trace()}
        assert "session-opened" in kinds
        assert "session-closed" in kinds
        assert "seek-started" in kinds
        assert "seek-completed" in kinds
    finally:
        set_replay_trace_enabled(False)


def test_seek_metric_increments(canonical_session: Path) -> None:
    before = get_loader_metrics_snapshot().seeks_performed
    with ReplayEventLoader.open(canonical_session) as loader:
        loader.seek_to_sequence(4)
        loader.seek_to_sequence(8)
    after = get_loader_metrics_snapshot().seeks_performed
    assert after - before == 2
