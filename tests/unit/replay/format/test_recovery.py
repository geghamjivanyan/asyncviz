"""Malformed-frame isolation + recovery tests."""

from __future__ import annotations

from asyncviz.replay.format import (
    RecoveringDecoder,
    ReplayFrame,
    encode_frame,
    get_format_metrics_snapshot,
    recover_frames,
)


def _line(seq: int) -> str:
    return encode_frame(
        ReplayFrame.for_runtime_event(
            sequence=seq,
            monotonic_ns=seq * 10,
            payload_type="asyncio.task.created",
            payload={"task_id": f"t-{seq}"},
        ),
    )


def test_recover_frames_skips_malformed_lines() -> None:
    lines = [
        _line(1),
        "garbage line\n",
        _line(2),
        '{"not-a-frame":true}\n',
        _line(3),
    ]
    outcome = recover_frames(lines)
    assert outcome.recovered_count == 3
    assert outcome.discarded_count == 2
    assert [f.sequence for f in outcome.recovered_frames] == [1, 2, 3]


def test_recovering_decoder_streams_lazily() -> None:
    lines = [_line(1), "broken\n", _line(2)]
    decoder = RecoveringDecoder(lines)
    seqs = [f.sequence for f in decoder]
    assert seqs == [1, 2]
    assert decoder.recovered_count == 2
    assert len(decoder.discarded) == 1
    assert decoder.discarded[0].line_number == 2


def test_recovery_bumps_malformed_counter() -> None:
    lines = ["xxx\n", _line(1)]
    list(RecoveringDecoder(lines))
    snap = get_format_metrics_snapshot()
    assert snap.malformed_frames >= 1


def test_recover_frames_preserves_discard_line_numbers() -> None:
    lines = [_line(1), "junk\n", _line(2), "junk2\n", _line(3)]
    outcome = recover_frames(lines)
    assert [d.line_number for d in outcome.discarded] == [2, 4]
