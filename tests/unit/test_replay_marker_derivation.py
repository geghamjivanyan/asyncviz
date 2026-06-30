"""Tests for ``derive_markers_and_bookmarks``.

The derivation runs at bundle-open time and feeds the replay
broadcaster, so its contract — what makes it onto the timeline, what
gets bookmarked, what the wire shapes look like — is exercised here
without touching the launcher or websocket layer.
"""

from __future__ import annotations

from typing import Any

from asyncviz.dashboard.replay.replay_marker_derivation import (
    derive_markers_and_bookmarks,
)


def _ev(
    seq: int,
    et: str,
    *,
    mono: int | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "sequence": seq,
        "monotonic_ns": mono if mono is not None else seq * 1_000_000,
        "event_type": et,
        "payload": payload or {},
    }


def test_empty_stream_yields_empty_lists():
    markers, bookmarks = derive_markers_and_bookmarks([])
    assert markers == []
    assert bookmarks == []


def test_single_event_yields_runtime_started_bookmark():
    frames = [_ev(1, "asyncio.task.created")]
    _, bookmarks = derive_markers_and_bookmarks(frames)
    labels = [b["label"] for b in bookmarks]
    assert "Runtime started" in labels
    # No "Runtime stopped" — span is zero-length.
    assert "Runtime stopped" not in labels


def test_failed_task_emits_critical_warning_marker():
    frames = [
        _ev(1, "asyncio.task.created"),
        _ev(
            2,
            "asyncio.task.failed",
            payload={"exception_type": "RuntimeError", "exception_message": "boom"},
        ),
        _ev(3, "asyncio.task.created"),
    ]
    markers, bookmarks = derive_markers_and_bookmarks(frames)
    failure_markers = [m for m in markers if m["kind"] == "warning"]
    assert len(failure_markers) == 1
    failure = failure_markers[0]
    assert failure["severity"] == "critical"
    assert failure["sequence"] == 2
    assert "RuntimeError" in failure["label"]
    assert failure["description"] == "boom"

    labels = {b["label"] for b in bookmarks}
    assert {"Runtime started", "First warning", "First failure"} <= labels


def test_queue_saturation_emits_saturation_marker_and_bookmark():
    frames = [
        _ev(1, "asyncio.task.created"),
        _ev(
            2,
            "asyncio.queue.saturation.detected",
            payload={"queue_id": "ingest"},
        ),
    ]
    markers, bookmarks = derive_markers_and_bookmarks(frames)
    sat = [m for m in markers if m["kind"] == "saturation"]
    assert len(sat) == 1
    assert sat[0]["severity"] == "critical"
    assert "ingest" in sat[0]["label"]
    assert any(b["label"] == "First saturation" for b in bookmarks)


def test_loop_blocked_emits_blocking_marker_and_bookmark():
    frames = [
        _ev(1, "asyncio.task.created"),
        _ev(2, "asyncio.loop.blocked", payload={"duration_ms": 42}),
    ]
    markers, bookmarks = derive_markers_and_bookmarks(frames)
    blocking = [m for m in markers if m["kind"] == "blocking"]
    assert len(blocking) == 1
    assert blocking[0]["severity"] == "critical"
    assert "42" in blocking[0]["label"]
    assert any(b["label"] == "Blocking detected" for b in bookmarks)


def test_pressure_change_to_info_level_does_not_emit():
    frames = [
        _ev(1, "asyncio.task.created"),
        _ev(
            2,
            "asyncio.queue.pressure.changed",
            payload={"queue_id": "q", "new_level": "nominal"},
        ),
    ]
    markers, _ = derive_markers_and_bookmarks(frames)
    assert all(m["kind"] != "saturation" for m in markers)


def test_max_markers_cap_keeps_first_n():
    frames = [_ev(0, "asyncio.task.created")]
    for i in range(1, 20):
        frames.append(
            _ev(
                i,
                "asyncio.task.failed",
                payload={"exception_type": f"E{i}", "exception_message": "x"},
            ),
        )
    markers, _ = derive_markers_and_bookmarks(frames, max_markers=5, snapshot_buckets=0)
    real = [m for m in markers if m["kind"] == "warning"]
    assert len(real) == 5
    # First 5 are kept — labels should reference E1..E5.
    labels = [m["label"] for m in real]
    assert "E1" in labels[0]
    assert "E5" in labels[4]


def test_snapshot_buckets_distribute_across_span():
    frames = [_ev(i, "asyncio.task.created") for i in range(0, 1000)]
    markers, _ = derive_markers_and_bookmarks(frames, snapshot_buckets=10)
    snaps = [m for m in markers if m["kind"] == "checkpoint"]
    assert len(snaps) == 10
    # Strictly increasing sequence — anchors should span the recording.
    seqs = [m["sequence"] for m in snaps]
    assert seqs == sorted(seqs)
    assert seqs[0] == 0
    assert seqs[-1] >= 800


def test_snapshot_buckets_skipped_on_degenerate_span():
    frames = [_ev(1, "asyncio.task.created")]
    markers, _ = derive_markers_and_bookmarks(frames, snapshot_buckets=10)
    assert all(m["kind"] != "checkpoint" for m in markers)


def test_runtime_stopped_bookmark_emitted_when_span_nonzero():
    frames = [
        _ev(1, "asyncio.task.created", mono=100),
        _ev(50, "asyncio.task.created", mono=999),
    ]
    _, bookmarks = derive_markers_and_bookmarks(frames)
    stop = [b for b in bookmarks if b["label"] == "Runtime stopped"]
    assert len(stop) == 1
    assert stop[0]["sequence"] == 50
    assert stop[0]["monotonic_ns"] == 999


def test_malformed_frames_are_skipped():
    frames = [
        {"event_type": "asyncio.task.created"},  # missing sequence + monotonic
        _ev(1, "asyncio.task.created"),
        {"sequence": 2, "monotonic_ns": 2_000_000},  # missing event_type
        _ev(3, "asyncio.queue.saturation.detected", payload={"queue_id": "q"}),
    ]
    markers, _ = derive_markers_and_bookmarks(frames)
    sat = [m for m in markers if m["kind"] == "saturation"]
    assert len(sat) == 1
    assert sat[0]["sequence"] == 3


def test_marker_wire_shape_contract():
    """Pin the exact keys the frontend bridge consumes."""
    frames = [_ev(1, "asyncio.task.failed", payload={"exception_type": "X"})]
    markers, bookmarks = derive_markers_and_bookmarks(frames, snapshot_buckets=0)
    marker = next(m for m in markers if m["kind"] == "warning")
    assert set(marker.keys()) >= {
        "id",
        "kind",
        "severity",
        "sequence",
        "monotonic_ns",
        "label",
    }
    assert isinstance(marker["id"], str)
    assert isinstance(marker["sequence"], int)
    assert isinstance(marker["monotonic_ns"], int)

    bm = next(b for b in bookmarks if b["label"] == "Runtime started")
    assert set(bm.keys()) >= {
        "id",
        "label",
        "sequence",
        "monotonic_ns",
        "created_at_ms",
    }
