"""Backpressure + line-size safety tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.format import (
    MAX_FRAME_LINE_BYTES,
    FrameTooLargeError,
    OverflowGuard,
    get_format_metrics_snapshot,
    guard_line_length,
)


def test_guard_line_length_accepts_normal_line() -> None:
    guard_line_length("hello world\n")  # no raise


def test_guard_line_length_rejects_oversized_string() -> None:
    huge = "x" * (MAX_FRAME_LINE_BYTES + 1)
    with pytest.raises(FrameTooLargeError):
        guard_line_length(huge)
    snap = get_format_metrics_snapshot()
    assert snap.backpressure_events >= 1


def test_guard_line_length_rejects_oversized_bytes() -> None:
    huge = b"x" * (MAX_FRAME_LINE_BYTES + 1)
    with pytest.raises(FrameTooLargeError):
        guard_line_length(huge)


def test_overflow_guard_aggregates_within_window() -> None:
    guard = OverflowGuard(window_seconds=5.0, threshold=3)
    assert guard.trip() is False
    assert guard.trip() is False
    assert guard.trip() is True  # 3rd within window


def test_overflow_guard_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter([0.0, 0.1, 10.0, 10.1])
    monkeypatch.setattr(
        "asyncviz.replay.format.ndjson_backpressure.time.monotonic",
        lambda: next(times),
    )
    guard = OverflowGuard(window_seconds=1.0, threshold=3)
    guard.trip()  # t=0.0
    guard.trip()  # t=0.1
    # t=10.0 — outside window; counter resets.
    assert guard.trip() is False
    # t=10.1 — still inside new window; still under threshold.
    assert guard.trip() is False
