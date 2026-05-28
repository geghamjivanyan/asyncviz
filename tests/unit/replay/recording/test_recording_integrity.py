"""Integrity validation + repair tests."""

from __future__ import annotations

import json
from pathlib import Path

from asyncviz.replay.recording import (
    compute_chunk_hash,
    count_chunk_events,
    repair_partial_tail,
    verify_chunk_hash,
)


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_repair_returns_noop_for_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "events.ndjson"
    result = repair_partial_tail(path)
    assert result.truncated_bytes == 0
    assert result.lines_kept == 0


def test_repair_noop_for_clean_file(tmp_path: Path) -> None:
    path = tmp_path / "events.ndjson"
    _write_lines(path, [json.dumps({"sequence": i}) for i in range(1, 4)])
    pre_size = path.stat().st_size
    result = repair_partial_tail(path)
    assert result.truncated_bytes == 0
    assert result.lines_kept == 3
    assert path.stat().st_size == pre_size


def test_repair_truncates_partial_trailing_line(tmp_path: Path) -> None:
    path = tmp_path / "events.ndjson"
    good = json.dumps({"sequence": 1})
    # Simulate a crash mid-write: append a partial line without a newline.
    path.write_text(good + "\n" + '{"sequence": 2', encoding="utf-8")
    result = repair_partial_tail(path)
    assert result.truncated_bytes > 0
    assert result.lines_kept == 1
    # The good line survives.
    assert path.read_text(encoding="utf-8").strip() == good


def test_repair_truncates_malformed_trailing_line(tmp_path: Path) -> None:
    path = tmp_path / "events.ndjson"
    good = json.dumps({"sequence": 1})
    # Complete line ending in newline, but body is invalid JSON.
    path.write_text(good + "\n" + "not-json\n", encoding="utf-8")
    result = repair_partial_tail(path)
    assert result.truncated_bytes > 0
    assert path.read_text(encoding="utf-8").strip() == good


def test_count_chunk_events_matches_writer(tmp_path: Path) -> None:
    path = tmp_path / "events.ndjson"
    _write_lines(path, [json.dumps({"sequence": i}) for i in range(1, 5)])
    assert count_chunk_events(path) == 4


def test_hash_verification_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "events.ndjson"
    _write_lines(path, [json.dumps({"sequence": i}) for i in range(1, 3)])
    digest = compute_chunk_hash(path)
    assert verify_chunk_hash(path, digest)
    assert not verify_chunk_hash(path, "0" * 64)
