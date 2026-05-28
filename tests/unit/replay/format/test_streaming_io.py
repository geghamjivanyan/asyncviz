"""Streaming reader / file writer / multi-file iteration tests."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.format import (
    NdjsonFrameReader,
    NdjsonFrameWriter,
    ReplayFrame,
    StreamingFrameReader,
    encode_frame,
    iter_lines,
    iter_lines_multi,
    make_runtime_event_frame,
)
from asyncviz.runtime.events.models import TaskCreatedEvent


def _evt_frame(seq: int) -> ReplayFrame:
    return make_runtime_event_frame(
        sequence=seq,
        monotonic_ns=seq * 10,
        event=TaskCreatedEvent(task_id=f"t-{seq}", task_name=f"n-{seq}"),
    )


def test_writer_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "frames.ndjson"
    with NdjsonFrameWriter(path) as writer:
        writer.append_many(_evt_frame(i) for i in range(1, 6))
    with NdjsonFrameReader(path) as reader:
        frames = list(reader)
    assert [f.sequence for f in frames] == [1, 2, 3, 4, 5]


def test_writer_with_digest_produces_stable_hash(tmp_path: Path) -> None:
    path = tmp_path / "a.ndjson"
    # Build frames once — event_id is generated per-instance, so
    # recreating the frame would yield different bytes each time.
    frames = [_evt_frame(i) for i in range(1, 4)]
    with NdjsonFrameWriter(path, track_digest=True) as writer:
        for frame in frames:
            writer.append(frame)
        first_digest = writer.hexdigest()
    import hashlib
    hasher = hashlib.sha256()
    for frame in frames:
        hasher.update(encode_frame(frame).encode("utf-8"))
    assert first_digest == hasher.hexdigest()


def test_reader_skips_malformed_lines(tmp_path: Path) -> None:
    path = tmp_path / "mixed.ndjson"
    path.write_text(
        encode_frame(_evt_frame(1))
        + "garbage line\n"
        + encode_frame(_evt_frame(2))
        + '{"bad":true}\n'
        + encode_frame(_evt_frame(3)),
        encoding="utf-8",
    )
    with NdjsonFrameReader(path) as reader:
        frames = list(reader)
    assert [f.sequence for f in frames] == [1, 2, 3]
    assert reader.report.discarded_count == 2
    assert reader.report.lines_read == 5


def test_iter_lines_skips_unterminated_tail(tmp_path: Path) -> None:
    path = tmp_path / "partial.ndjson"
    path.write_text(encode_frame(_evt_frame(1)) + "incomplete-no-newline", encoding="utf-8")
    lines = list(iter_lines(path))
    assert len(lines) == 1


def test_iter_lines_multi_concatenates_in_order(tmp_path: Path) -> None:
    chunk1 = tmp_path / "01.ndjson"
    chunk2 = tmp_path / "02.ndjson"
    chunk1.write_text(encode_frame(_evt_frame(1)) + encode_frame(_evt_frame(2)), encoding="utf-8")
    chunk2.write_text(encode_frame(_evt_frame(3)), encoding="utf-8")
    seqs = []
    from asyncviz.replay.format import decode_frame
    for line in iter_lines_multi([chunk1, chunk2]):
        seqs.append(decode_frame(line).sequence)
    assert seqs == [1, 2, 3]


def test_streaming_frame_reader_yields_in_order(tmp_path: Path) -> None:
    chunk = tmp_path / "stream.ndjson"
    chunk.write_text("".join(encode_frame(_evt_frame(i)) for i in range(1, 11)), encoding="utf-8")
    reader = StreamingFrameReader([chunk])
    seqs = [f.sequence for f in reader]
    assert seqs == list(range(1, 11))
    stats = reader.stats()
    assert stats.frames_yielded == 10
    assert stats.lines_dropped == 0
