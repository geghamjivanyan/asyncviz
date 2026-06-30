"""Crash recovery scenarios."""

from __future__ import annotations

import json
from pathlib import Path

from asyncviz.replay.recording import (
    RecordingConfig,
    RecordingWriter,
    iter_chunk_lines,
    recover_session,
)


def _make_payload(seq: int) -> dict:
    return {
        "sequence": seq,
        "event_id": f"evt-{seq}",
        "event_type": "asyncio.task.created",
        "monotonic_ns": seq * 1_000_000,
        "payload": {"task_id": f"t-{seq}"},
    }


def test_recover_session_reports_no_op_on_clean_directory(tmp_path: Path) -> None:
    cfg = RecordingConfig(root_dir=tmp_path, snapshot_on_start=False, snapshot_on_stop=False)
    session = tmp_path / "clean"
    session.mkdir()
    writer = RecordingWriter(session, config=cfg)
    for i in range(1, 4):
        writer.enqueue(sequence=i, payload=_make_payload(i))
    writer.flush()
    writer.stop()
    report = recover_session(session)
    assert report.repaired_chunks == 0
    assert report.truncated_bytes_total == 0
    assert report.inferred_event_count == 3
    assert report.inferred_last_sequence == 3


def test_recover_session_truncates_partial_tail(tmp_path: Path) -> None:
    cfg = RecordingConfig(root_dir=tmp_path, snapshot_on_start=False, snapshot_on_stop=False)
    session = tmp_path / "crash"
    session.mkdir()
    writer = RecordingWriter(session, config=cfg)
    for i in range(1, 4):
        writer.enqueue(sequence=i, payload=_make_payload(i))
    writer.flush()
    writer.stop()
    chunk = session / "events" / "000001.ndjson"
    # Simulate a crash mid-write by appending a partial trailing line.
    with chunk.open("a", encoding="utf-8") as f:
        f.write('{"sequence": 99, "partial":')  # no newline, malformed
    report = recover_session(session)
    assert report.repaired_chunks == 1
    assert report.truncated_bytes_total > 0
    assert report.inferred_event_count == 3
    # The good events survive after repair.
    lines = list(iter_chunk_lines(chunk))
    assert len(lines) == 3
    sequences = [json.loads(line)["sequence"] for line in lines]
    assert sequences == [1, 2, 3]


def test_writer_reopens_existing_chunk_after_crash(tmp_path: Path) -> None:
    """First writer dies → second writer points at the same session +
    appends after recovery. Sequence numbers and events from the
    first session must survive."""
    cfg = RecordingConfig(
        root_dir=tmp_path,
        snapshot_on_start=False,
        snapshot_on_stop=False,
    )
    session = tmp_path / "reopen"
    session.mkdir()
    writer1 = RecordingWriter(session, config=cfg)
    for i in range(1, 4):
        writer1.enqueue(sequence=i, payload=_make_payload(i))
    writer1.flush()
    # Don't call stop() — simulate abrupt termination.
    writer2 = RecordingWriter(session, config=cfg)
    for i in range(4, 7):
        writer2.enqueue(sequence=i, payload=_make_payload(i))
    writer2.flush()
    writer2.stop()
    chunk = session / "events" / "000001.ndjson"
    lines = list(iter_chunk_lines(chunk))
    sequences = [json.loads(line)["sequence"] for line in lines]
    assert sequences == [1, 2, 3, 4, 5, 6]
