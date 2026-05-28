"""Validation + backpressure safety tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading import (
    BufferCap,
    ReplayBufferOverflowError,
    enforce_buffer_cap,
    validate_loader_stream,
)


def _frame(seq: int) -> ReplayFrame:
    return ReplayFrame.for_runtime_event(
        sequence=seq,
        monotonic_ns=seq * 10,
        payload_type="asyncio.task.created",
        payload={"task_id": f"t-{seq}"},
    )


def test_validate_loader_stream_drops_duplicates() -> None:
    frames = [_frame(1), _frame(1), _frame(2)]
    iterator, report = validate_loader_stream(frames, allow_gaps=True)
    out = list(iterator)
    assert [f.sequence for f in out] == [1, 2]
    assert report.issue_count == 1
    assert report.issues[0].reason.startswith("duplicate")


def test_validate_loader_stream_drops_out_of_order() -> None:
    frames = [_frame(5), _frame(3)]
    iterator, report = validate_loader_stream(frames, allow_gaps=True)
    out = list(iterator)
    assert [f.sequence for f in out] == [5]
    assert report.issue_count == 1


def test_validate_loader_stream_allows_gaps_by_default() -> None:
    frames = [_frame(1), _frame(5), _frame(7)]
    iterator, report = validate_loader_stream(frames, allow_gaps=True)
    out = list(iterator)
    assert [f.sequence for f in out] == [1, 5, 7]
    assert report.clean


def test_validate_loader_stream_strict_raises() -> None:
    frames = [_frame(1), _frame(1)]
    iterator, _ = validate_loader_stream(frames, strict=True)
    with pytest.raises(ValueError):
        list(iterator)


def test_buffer_cap_raises_on_overflow() -> None:
    cap = BufferCap(capacity=3)
    cap.add(1)
    cap.add(1)
    cap.add(1)
    with pytest.raises(ReplayBufferOverflowError):
        cap.add(1)


def test_buffer_cap_remove_lowers_depth() -> None:
    cap = BufferCap(capacity=3)
    cap.add(2)
    cap.remove(1)
    assert cap.depth == 1


def test_enforce_buffer_cap_raises_at_threshold() -> None:
    with pytest.raises(ReplayBufferOverflowError):
        enforce_buffer_cap(100, 100)
