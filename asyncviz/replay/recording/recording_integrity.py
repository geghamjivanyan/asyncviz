"""Integrity validation + repair helpers for NDJSON event chunks.

The events file is plain newline-delimited JSON. A crash mid-write
can leave one of two failure modes:

  1. A trailing partial line (process killed while writing the last
     event). We detect this by checking the final byte — if it isn't
     ``\\n`` the tail is incomplete and gets truncated.
  2. A trailing line whose JSON is invalid (rare on POSIX with single
     ``write()`` calls < PIPE_BUF, but possible on Windows with
     interleaved partial writes). Detected by attempting to parse the
     last line; on failure, truncate.

Both cases are recoverable without losing prior events. The repaired
chunk is left exactly at the last fully-written newline, which is the
correct semantic anchor for an append-only log.

Integrity hashes (optional) are computed at chunk finalize time;
:func:`compute_chunk_hash` re-reads the file to verify against the
manifest on load.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RepairResult:
    """Outcome of a single repair pass over an events file."""

    path: Path
    initial_size: int
    repaired_size: int
    truncated_bytes: int
    lines_kept: int
    lines_dropped: int


def repair_partial_tail(path: Path) -> RepairResult:
    """Truncate any trailing partial line so the file ends on ``\\n``.

    Returns a :class:`RepairResult` describing what was kept. Safe to
    call when the file doesn't need repair — returns ``truncated_bytes=0``
    in that case.
    """
    if not path.exists():
        return RepairResult(path, 0, 0, 0, 0, 0)
    raw = path.read_bytes()
    initial_size = len(raw)
    if initial_size == 0:
        return RepairResult(path, 0, 0, 0, 0, 0)

    # Trim the tail until we land on a ``\n``-terminated line whose
    # JSON parses. We work backwards because the common case is a
    # single partial line at EOF.
    repaired_end = initial_size
    if raw[-1:] != b"\n":
        # find last newline
        last_nl = raw.rfind(b"\n")
        repaired_end = last_nl + 1 if last_nl >= 0 else 0
    # Now also validate the last full line — it might be complete on
    # disk but the JSON itself could be malformed (extremely rare but
    # we'd rather not propagate a bad line into replay).
    while repaired_end > 0:
        candidate_start = raw.rfind(b"\n", 0, repaired_end - 1) + 1
        line = raw[candidate_start : repaired_end - 1]
        if not line:
            break
        try:
            json.loads(line)
            break
        except json.JSONDecodeError:
            repaired_end = candidate_start

    if repaired_end == initial_size:
        # Already clean — no truncation.
        kept = raw.count(b"\n")
        return RepairResult(path, initial_size, initial_size, 0, kept, 0)

    truncated = initial_size - repaired_end
    repaired = raw[:repaired_end]
    path.write_bytes(repaired)
    kept = repaired.count(b"\n")
    dropped = 1  # we truncated at least one partial / bad line
    return RepairResult(path, initial_size, repaired_end, truncated, kept, dropped)


def count_chunk_events(path: Path) -> int:
    """Count fully-written newline-terminated lines in an NDJSON chunk."""
    if not path.exists():
        return 0
    return path.read_bytes().count(b"\n")


def compute_chunk_hash(path: Path) -> str:
    """SHA-256 of the chunk's bytes. Used for integrity checks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_chunk_hash(path: Path, expected: str) -> bool:
    """Verify ``path``'s content hash against ``expected``."""
    return compute_chunk_hash(path) == expected
