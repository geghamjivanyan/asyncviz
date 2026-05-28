"""Frame + stream integrity-hash tests."""

from __future__ import annotations

from asyncviz.replay.format import (
    ReplayFrame,
    StreamDigest,
    compute_frame_digest,
    encode_frame,
    verify_frame_digest,
)


def _frame(seq: int) -> ReplayFrame:
    return ReplayFrame.for_runtime_event(
        sequence=seq,
        monotonic_ns=seq * 100,
        payload_type="asyncio.task.created",
        payload={"task_id": f"t-{seq}"},
    )


def test_frame_digest_is_stable_across_calls() -> None:
    assert compute_frame_digest(_frame(1)) == compute_frame_digest(_frame(1))


def test_frame_digest_changes_with_payload() -> None:
    assert compute_frame_digest(_frame(1)) != compute_frame_digest(_frame(2))


def test_verify_frame_digest_round_trip() -> None:
    frame = _frame(7)
    expected = compute_frame_digest(frame)
    assert verify_frame_digest(frame, expected)


def test_verify_frame_digest_rejects_mismatch() -> None:
    frame = _frame(7)
    assert not verify_frame_digest(frame, "0" * 64)


def test_stream_digest_matches_concatenation() -> None:
    frames = [_frame(i) for i in range(1, 6)]
    digest = StreamDigest.fresh()
    for frame in frames:
        digest.update(frame)
    # Compute the equivalent hash by hand:
    import hashlib
    hasher = hashlib.sha256()
    for frame in frames:
        hasher.update(encode_frame(frame).encode("utf-8"))
    assert digest.hexdigest() == hasher.hexdigest()
    assert digest.frame_count == 5


def test_stream_digest_from_existing_seeds_correctly() -> None:
    frames = [_frame(1), _frame(2)]
    lines = [encode_frame(f) for f in frames]
    seeded = StreamDigest.from_existing(lines)
    fresh = StreamDigest.fresh()
    for frame in frames:
        fresh.update(frame)
    assert seeded.hexdigest() == fresh.hexdigest()
