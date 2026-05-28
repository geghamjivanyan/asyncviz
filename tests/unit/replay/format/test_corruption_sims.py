"""Corruption simulations — readers must isolate damage."""

from __future__ import annotations

from pathlib import Path

from asyncviz.replay.format import (
    NdjsonFrameReader,
    NdjsonFrameWriter,
    StreamingFrameReader,
    encode_frame,
    make_runtime_event_frame,
)
from asyncviz.runtime.events.models import TaskCreatedEvent


def _frame(seq: int):
    return make_runtime_event_frame(
        sequence=seq,
        monotonic_ns=seq,
        event=TaskCreatedEvent(task_id=f"t-{seq}", task_name=str(seq)),
    )


def test_truncated_tail_does_not_kill_stream(tmp_path: Path) -> None:
    path = tmp_path / "torn.ndjson"
    with NdjsonFrameWriter(path) as writer:
        for i in range(1, 4):
            writer.append(_frame(i))
    # Simulate a torn write by appending half a frame without newline.
    with path.open("a", encoding="utf-8") as f:
        f.write('{"schema_version":1,"frame_type":"runtime_eve')
    with NdjsonFrameReader(path) as reader:
        frames = list(reader)
    assert [f.sequence for f in frames] == [1, 2, 3]


def test_interspersed_garbage_lines_isolated(tmp_path: Path) -> None:
    path = tmp_path / "interspersed.ndjson"
    payload = (
        encode_frame(_frame(1))
        + "garbage1\n"
        + encode_frame(_frame(2))
        + '{"missing":"keys"}\n'
        + encode_frame(_frame(3))
        + "not-json-at-all\n"
        + encode_frame(_frame(4))
    )
    path.write_text(payload, encoding="utf-8")
    with NdjsonFrameReader(path) as reader:
        frames = list(reader)
    assert [f.sequence for f in frames] == [1, 2, 3, 4]
    assert reader.report.discarded_count == 3


def test_streaming_reader_continues_after_corruption(tmp_path: Path) -> None:
    path = tmp_path / "streamy.ndjson"
    with NdjsonFrameWriter(path) as writer:
        for i in range(1, 11):
            writer.append(_frame(i))
    # Splice a malformed line into the middle.
    raw = path.read_text(encoding="utf-8")
    halves = raw.split("\n", 3)
    splice = halves[0] + "\n" + halves[1] + "\nINVALID-LINE\n" + halves[2] + "\n" + halves[3]
    path.write_text(splice, encoding="utf-8")
    reader = StreamingFrameReader([path])
    seqs = [f.sequence for f in reader]
    # Order preserved + at least 9 frames survive.
    assert seqs == sorted(seqs)
    assert len(seqs) >= 9


def test_empty_file_yields_no_frames(tmp_path: Path) -> None:
    path = tmp_path / "empty.ndjson"
    path.touch()
    with NdjsonFrameReader(path) as reader:
        assert list(reader) == []
