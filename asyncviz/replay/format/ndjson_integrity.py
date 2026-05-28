"""Integrity hashing for replay frames.

Two scopes:

* **Per-frame digest** — SHA-256 of one canonical-JSON line. Useful
  when a frame needs to be deduplicated against an external store
  (e.g. an object-store ingestion that wants to know whether it has
  already seen this frame).
* **Per-stream digest** — a running SHA-256 over the concatenation
  of all canonical frame lines, updated incrementally as frames are
  encoded. Provides a single tamper-evident value for an entire
  recording without re-reading the file.

We use SHA-256 to match the chunk-level hashes already produced by
the recording layer, so a recording's frame-level + chunk-level +
manifest-level hashes all live in the same algorithmic family.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from asyncviz.replay.format.ndjson_frame import ReplayFrame
from asyncviz.replay.format.ndjson_observability import get_format_metrics
from asyncviz.replay.format.ndjson_serialization import encode_frame
from asyncviz.replay.format.ndjson_tracing import record_ndjson_trace


def compute_frame_digest(frame: ReplayFrame) -> str:
    """SHA-256 hex digest of a frame's canonical line bytes
    (including the trailing newline). Stable across runs."""
    line = encode_frame(frame)
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def verify_frame_digest(frame: ReplayFrame, expected: str) -> bool:
    """Constant-time digest check.

    On failure, the integrity metric is bumped + a trace is recorded.
    """
    actual = compute_frame_digest(frame)
    ok = hashlib.sha256(actual.encode("ascii")).digest() == hashlib.sha256(
        expected.encode("ascii"),
    ).digest()
    if not ok:
        get_format_metrics().record_integrity_failure()
        record_ndjson_trace("integrity-failed", f"seq={frame.sequence} type={frame.frame_type}")
    return ok


@dataclass(slots=True)
class StreamDigest:
    """Incremental SHA-256 over a frame stream's canonical bytes.

    Use :meth:`update` per frame as you write/encode it, then
    :meth:`hexdigest` for the final value. The accumulator is
    appendable — restarting a recording can resume from the prior
    digest by seeding ``initial_digest_hex``."""

    _hasher: hashlib._Hash
    _frame_count: int = 0

    @classmethod
    def fresh(cls) -> StreamDigest:
        return cls(_hasher=hashlib.sha256())

    @classmethod
    def from_existing(cls, initial_lines: Iterable[str]) -> StreamDigest:
        """Build a digest pre-populated with already-encoded lines."""
        hasher = hashlib.sha256()
        count = 0
        for line in initial_lines:
            if not line.endswith("\n"):
                line += "\n"
            hasher.update(line.encode("utf-8"))
            count += 1
        return cls(_hasher=hasher, _frame_count=count)

    def update(self, frame: ReplayFrame) -> None:
        line = encode_frame(frame)
        self._hasher.update(line.encode("utf-8"))
        self._frame_count += 1

    def update_line(self, encoded_line: str) -> None:
        """Skip re-encoding when caller already has the canonical line."""
        if not encoded_line.endswith("\n"):
            encoded_line += "\n"
        self._hasher.update(encoded_line.encode("utf-8"))
        self._frame_count += 1

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def hexdigest(self) -> str:
        return self._hasher.hexdigest()
