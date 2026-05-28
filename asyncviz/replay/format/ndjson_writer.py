"""High-level append-only NDJSON frame writer.

This wraps a file handle + the canonical encoder. It is distinct from
:class:`asyncviz.replay.recording.RecordingWriter` (which owns the
multi-chunk rotation logic): this writer is a single-file,
single-process façade that's useful for offline replay export, test
fixtures, and one-off recording transforms.

Crash-safety properties of this writer:

* Lines are flushed to the underlying buffer on every call so a
  ``KeyboardInterrupt`` mid-stream still leaves the previous frame
  whole on disk.
* The optional ``StreamDigest`` integration produces a tamper-evident
  hash over everything appended — bumped on every successful append.
"""

from __future__ import annotations

import io
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from types import TracebackType

from asyncviz.replay.format.ndjson_frame import ReplayFrame
from asyncviz.replay.format.ndjson_integrity import StreamDigest
from asyncviz.replay.format.ndjson_serialization import encode_frame


class NdjsonFrameWriter:
    """Append-only NDJSON writer over a single file path."""

    __slots__ = ("_digest", "_fh", "_path", "_track_digest")

    def __init__(self, path: Path, *, track_digest: bool = False) -> None:
        self._path = path
        self._track_digest = track_digest
        self._digest: StreamDigest | None = StreamDigest.fresh() if track_digest else None
        self._fh: io.TextIOWrapper | None = None

    # ── lifecycle ─────────────────────────────────────────────────

    def open(self) -> NdjsonFrameWriter:
        if self._fh is not None:
            return self
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("a", encoding="utf-8", buffering=8192)
        return self

    def close(self) -> None:
        if self._fh is None:
            return
        with suppress(Exception):
            self._fh.flush()
            self._fh.close()
        self._fh = None

    def __enter__(self) -> NdjsonFrameWriter:
        return self.open()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ── append ────────────────────────────────────────────────────

    def append(self, frame: ReplayFrame) -> int:
        """Encode + append one frame. Returns bytes written."""
        if self._fh is None:
            self.open()
        line = encode_frame(frame)
        assert self._fh is not None
        self._fh.write(line)
        self._fh.flush()
        if self._digest is not None:
            self._digest.update_line(line)
        return len(line.encode("utf-8"))

    def append_many(self, frames: Iterable[ReplayFrame]) -> int:
        """Append every frame in ``frames``. Returns total bytes."""
        total = 0
        for frame in frames:
            total += self.append(frame)
        return total

    # ── digest accessor ───────────────────────────────────────────

    @property
    def digest(self) -> StreamDigest | None:
        return self._digest

    def hexdigest(self) -> str | None:
        return self._digest.hexdigest() if self._digest is not None else None
