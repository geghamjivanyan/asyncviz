"""Filter algebra + windowing semantics."""

from __future__ import annotations

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading import (
    ReplayWindow,
    all_of,
    any_of,
    by_event_type,
    by_frame_type,
    by_sequence_range,
    by_timestamp_range,
    not_,
)


def _frame(seq: int, payload_type: str = "asyncio.task.created", ts: int = 0) -> ReplayFrame:
    return ReplayFrame.for_runtime_event(
        sequence=seq,
        monotonic_ns=ts or seq * 100,
        payload_type=payload_type,
        payload={"task_id": f"t-{seq}"},
    )


def test_by_event_type_matches() -> None:
    f = by_event_type("asyncio.task.created")
    assert f(_frame(1))
    assert not f(_frame(1, payload_type="asyncio.task.completed"))


def test_by_sequence_range_inclusive() -> None:
    f = by_sequence_range(3, 5)
    assert not f(_frame(2))
    assert f(_frame(3))
    assert f(_frame(5))
    assert not f(_frame(6))


def test_by_sequence_range_unbounded_above() -> None:
    f = by_sequence_range(3)
    assert f(_frame(100))


def test_by_timestamp_range() -> None:
    f = by_timestamp_range(500, 800)
    assert not f(_frame(1))  # ts=100
    assert f(_frame(5))  # ts=500
    assert f(_frame(8))  # ts=800
    assert not f(_frame(9))  # ts=900


def test_by_frame_type_matches_envelope() -> None:
    f = by_frame_type("runtime_event")
    assert f(_frame(1))


def test_all_of_combines_with_and() -> None:
    f = all_of(by_sequence_range(2, 9), by_event_type("asyncio.task.created"))
    assert f(_frame(3))
    assert not f(_frame(3, payload_type="asyncio.task.completed"))
    assert not f(_frame(10))


def test_any_of_combines_with_or() -> None:
    f = any_of(by_sequence_range(0, 1), by_sequence_range(8, 10))
    assert f(_frame(1))
    assert f(_frame(9))
    assert not f(_frame(5))


def test_not_inverts() -> None:
    f = not_(by_sequence_range(3, 5))
    assert f(_frame(1))
    assert not f(_frame(4))
    assert f(_frame(10))


def test_replay_window_contains_inclusive() -> None:
    w = ReplayWindow.for_sequences(2, 4)
    assert not w.contains(_frame(1))
    assert w.contains(_frame(2))
    assert w.contains(_frame(4))
    assert not w.contains(_frame(5))


def test_replay_window_above_window_signals_early_stop() -> None:
    w = ReplayWindow.for_sequences(2, 4)
    assert w.above_window(_frame(5))
    assert not w.above_window(_frame(4))


def test_replay_window_below_window_signals_skip() -> None:
    w = ReplayWindow.for_sequences(3)
    assert w.below_window(_frame(1))
    assert not w.below_window(_frame(3))


def test_replay_window_timestamp_form() -> None:
    w = ReplayWindow.for_timestamps(300, 700)
    assert not w.contains(_frame(2))  # ts=200
    assert w.contains(_frame(3))  # ts=300
    assert w.contains(_frame(7))  # ts=700
    assert not w.contains(_frame(8))  # ts=800
