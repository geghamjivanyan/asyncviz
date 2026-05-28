"""Tests for the :class:`RecorderBundleAdapter`.

The adapter is what the ``asyncviz replay`` CLI actually uses today
(the canonical :class:`ReplayEventLoader` rejects the recorder's
``bundle_id``-keyed manifest format until those layers are
reconciled). These tests guard the adapter's contract:

* yields one :class:`ReplayFrame` per event in the bundle,
* preserves wire shape (event_type at top of payload),
* exposes a non-None ``snapshot_index`` so the engine constructs
  cleanly,
* surfaces a sensible ``BundleSummary``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from asyncviz.cli.runtime.replay_bundle_adapter import RecorderBundleAdapter
from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading.replay_snapshot_index import ReplaySnapshotIndex

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RECORDINGS_DIR = _REPO_ROOT / "asyncviz-recordings"


def _find_recorder_bundle() -> Path | None:
    if not _RECORDINGS_DIR.is_dir():
        return None
    for entry in sorted(_RECORDINGS_DIR.iterdir()):
        if entry.is_dir() and entry.suffix == ".avz" and (entry / "manifest.json").is_file():
            return entry
    return None


def test_recorder_bundle_adapter_yields_frames() -> None:
    bundle = _find_recorder_bundle()
    if bundle is None:
        pytest.skip(
            "no recorder bundle available under asyncviz-recordings/; "
            "run 'asyncviz record' once to seed one",
        )
    adapter = RecorderBundleAdapter.open(bundle)
    try:
        summary = adapter.summary()
        assert summary.bundle_id
        assert summary.event_count > 0, "recorder bundle must contain events"

        frames = list(adapter.iter_frames())
        assert len(frames) > 0
        assert all(isinstance(f, ReplayFrame) for f in frames)

        # Every frame is a ``runtime_event`` (adapter only emits those)
        # with the wire-shape payload: ``event_type`` at the top, so
        # the SPA reducer routes them via the same path as live events.
        for frame in frames[:3]:
            assert frame.frame_type == "runtime_event"
            assert frame.payload.get("event_type") == frame.payload_type
            assert frame.sequence > 0
            assert frame.monotonic_ns > 0
    finally:
        adapter.close()


def test_recorder_bundle_adapter_exposes_empty_snapshot_index() -> None:
    """The engine wraps the loader's snapshot_index in SnapshotRuntime
    at construction. An empty index is the v1 contract — seek is
    surfaced as NotImplementedError so misuse is loud.
    """
    bundle = _find_recorder_bundle()
    if bundle is None:
        pytest.skip("no recorder bundle available")
    adapter = RecorderBundleAdapter.open(bundle)
    try:
        idx = adapter.snapshot_index
        assert isinstance(idx, ReplaySnapshotIndex)
        # Empty index — len + index access both work but yield nothing.
        assert len(idx.entries) == 0
    finally:
        adapter.close()


def test_recorder_bundle_adapter_rejects_missing_bundle() -> None:
    with pytest.raises(FileNotFoundError):
        RecorderBundleAdapter.open(Path("/nonexistent/bundle.avz"))


def test_recorder_bundle_adapter_seek_raises_for_now() -> None:
    bundle = _find_recorder_bundle()
    if bundle is None:
        pytest.skip("no recorder bundle available")
    adapter = RecorderBundleAdapter.open(bundle)
    try:
        # v1 scope: seek/snapshot-restore are NotImplementedError. The
        # engine constructs fine and play/pause/speed work — only seek
        # surfaces this error, and only when the operator triggers it.
        with pytest.raises(NotImplementedError):
            adapter.reconstruct_state_at(0)
    finally:
        adapter.close()
