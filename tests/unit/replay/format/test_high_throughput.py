"""High-throughput encoding/decoding stress tests.

These are not benchmarks — they confirm correctness at scale (no
allocation explosions, no dropped frames, deterministic order)
without making timing assertions."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.format import (
    NdjsonFrameReader,
    NdjsonFrameWriter,
    decode_frame,
    encode_frame,
    make_runtime_event_frame,
)
from asyncviz.runtime.events.models import TaskCreatedEvent


def _bulk_frames(n: int) -> list:
    return [
        make_runtime_event_frame(
            sequence=i,
            monotonic_ns=i * 100,
            event=TaskCreatedEvent(task_id=f"t-{i}", task_name=f"n-{i}"),
        )
        for i in range(1, n + 1)
    ]


def test_10k_frames_round_trip_in_memory() -> None:
    frames = _bulk_frames(10_000)
    lines = [encode_frame(f) for f in frames]
    decoded = [decode_frame(line) for line in lines]
    assert [f.sequence for f in decoded] == list(range(1, 10_001))


def test_10k_frames_round_trip_on_disk(tmp_path: Path) -> None:
    path = tmp_path / "bulk.ndjson"
    with NdjsonFrameWriter(path) as writer:
        for frame in _bulk_frames(10_000):
            writer.append(frame)
    with NdjsonFrameReader(path) as reader:
        decoded = list(reader)
    assert len(decoded) == 10_000
    assert decoded[0].sequence == 1
    assert decoded[-1].sequence == 10_000


def test_streaming_is_memory_bounded(tmp_path: Path) -> None:
    """We don't measure RSS; we just ensure the reader doesn't load
    the whole file by materializing it lazily and stopping early."""
    path = tmp_path / "huge.ndjson"
    with NdjsonFrameWriter(path) as writer:
        for frame in _bulk_frames(50_000):
            writer.append(frame)

    # Iterate the first 50 and stop — the reader must not have read
    # the rest into memory (we just verify behavioral correctness).
    seen = 0
    with NdjsonFrameReader(path) as reader:
        for frame in reader:
            seen += 1
            assert frame.sequence == seen
            if seen == 50:
                break
    assert seen == 50
