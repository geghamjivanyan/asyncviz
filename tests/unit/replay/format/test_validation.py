"""Validation tests — single frame + stream-level."""

from __future__ import annotations

from asyncviz.replay.format import (
    ReplayFrame,
    SequenceValidator,
    get_format_metrics_snapshot,
    validate_frame,
    validate_stream,
)


def _frame(seq: int, frame_type: str = "runtime_event") -> ReplayFrame:
    return ReplayFrame(
        schema_version=1,
        frame_type=frame_type,  # type: ignore[arg-type]
        sequence=seq,
        monotonic_ns=seq * 10,
        payload_type="asyncio.task.created",
        payload={"task_id": f"t-{seq}"},
    )


def test_validate_frame_accepts_canonical_frame() -> None:
    report = validate_frame(_frame(1))
    assert report.valid
    assert report.issues == ()


def test_validate_frame_rejects_unknown_frame_type() -> None:
    bad = _frame(1, frame_type="something-unknown")
    report = validate_frame(bad)
    assert not report.valid
    assert any("unknown frame_type" in iss for iss in report.issues)


def test_validate_frame_rejects_negative_sequence() -> None:
    frame = ReplayFrame(
        schema_version=1,
        frame_type="runtime_event",
        sequence=-5,
        monotonic_ns=1,
        payload_type="x",
        payload={},
    )
    report = validate_frame(frame)
    assert not report.valid


def test_sequence_validator_accepts_monotonic_no_gaps() -> None:
    sv = SequenceValidator()
    for i in range(1, 6):
        clean, reason = sv.observe(_frame(i))
        assert clean, reason


def test_sequence_validator_flags_duplicates() -> None:
    sv = SequenceValidator()
    sv.observe(_frame(1))
    clean, reason = sv.observe(_frame(1))
    assert not clean
    assert "duplicate" in reason


def test_sequence_validator_flags_gaps_when_disallowed() -> None:
    sv = SequenceValidator(allow_gaps=False)
    sv.observe(_frame(1))
    clean, reason = sv.observe(_frame(3))
    assert not clean
    assert "gap" in reason


def test_sequence_validator_allows_gaps_when_opted_in() -> None:
    sv = SequenceValidator(allow_gaps=True)
    sv.observe(_frame(1))
    clean, reason = sv.observe(_frame(3))
    assert clean, reason


def test_sequence_validator_flags_backwards_sequences() -> None:
    sv = SequenceValidator()
    sv.observe(_frame(5))
    clean, reason = sv.observe(_frame(4))
    assert not clean
    assert "strictly after" in reason


def test_validate_stream_yields_per_frame_verdicts() -> None:
    frames = [_frame(1), _frame(1), _frame(3)]
    results = list(validate_stream(frames, allow_gaps=False))
    assert len(results) == 3
    assert results[0][1] is True
    assert results[1][1] is False  # dup
    assert results[2][1] is False  # gap


def test_validation_bumps_metrics() -> None:
    sv = SequenceValidator()
    sv.observe(_frame(1))
    sv.observe(_frame(1))  # duplicate
    sv.observe(_frame(3))  # gap
    snap = get_format_metrics_snapshot()
    assert snap.duplicate_sequences >= 1
    assert snap.sequence_violations >= 1
