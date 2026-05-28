"""Lazy, line-oriented streaming readers for the replay format.

The streaming layer's job is to feed the decoder one line at a time
without materializing the whole file. Three flavors live here:

* :func:`iter_lines` — generator over text lines of one file.
* :func:`iter_lines_multi` — generator across an ordered list of
  files (chunks of a single recording).
* :class:`StreamingFrameReader` — high-level wrapper that ties
  line-iteration to per-line size-guarding + recovering decode.

All readers are *pull-based*: callers drive iteration so they can
backpressure naturally and stop early without burning CPU on the
rest of the recording.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from asyncviz.replay.format.ndjson_backpressure import (
    FrameTooLargeError,
    guard_line_length,
)
from asyncviz.replay.format.ndjson_deserialization import (
    FrameDecodingError,
    decode_frame,
)
from asyncviz.replay.format.ndjson_frame import ReplayFrame
from asyncviz.replay.format.ndjson_observability import get_format_metrics
from asyncviz.replay.format.ndjson_tracing import record_ndjson_trace


def iter_lines(path: Path, *, encoding: str = "utf-8") -> Iterator[str]:
    """Yield the fully-written lines (with the trailing newline
    stripped) from a single NDJSON file.

    Lines without a terminating ``\\n`` are skipped — that's the
    invariant the recording layer's integrity logic upholds, and
    skipping torn lines defensively is cheap insurance against
    callers who didn't run the recovery step.
    """
    if not path.exists():
        return
    with path.open("r", encoding=encoding) as fh:
        for line in fh:
            if not line.endswith("\n"):
                continue
            yield line.rstrip("\n")


def iter_lines_multi(paths: Iterable[Path], *, encoding: str = "utf-8") -> Iterator[str]:
    """Yield lines across an ordered iterable of chunk paths."""
    for path in paths:
        record_ndjson_trace("stream-opened", str(path))
        yield from iter_lines(path, encoding=encoding)
        record_ndjson_trace("stream-closed", str(path))


@dataclass(frozen=True, slots=True)
class StreamingReadStats:
    """Lightweight stats for a streaming pass."""

    lines_read: int
    frames_yielded: int
    lines_dropped: int


class StreamingFrameReader:
    """High-level wrapper around line iteration + frame decoding.

    Designed for live-replay tooling: open it, iterate, and the
    underlying file handle is closed when the iterator is exhausted
    or garbage-collected. Malformed lines are dropped without
    halting the stream so a single corrupt line doesn't kill a
    long-running replay.
    """

    __slots__ = ("_dropped", "_frames", "_lines", "_lines_read", "_paths", "_strict")

    def __init__(self, paths: Iterable[Path], *, strict: bool = False) -> None:
        self._paths = list(paths)
        self._strict = strict
        self._lines_read = 0
        self._frames = 0
        self._dropped = 0
        self._lines: Iterator[str] | None = None

    def __iter__(self) -> Iterator[ReplayFrame]:
        for line in iter_lines_multi(self._paths):
            self._lines_read += 1
            try:
                guard_line_length(line)
            except FrameTooLargeError:
                self._dropped += 1
                get_format_metrics().record_malformed_frame()
                if self._strict:
                    raise
                continue
            try:
                frame = decode_frame(line)
            except FrameDecodingError:
                self._dropped += 1
                if self._strict:
                    raise
                continue
            self._frames += 1
            yield frame
        # Best-effort cleanup if the consumer abandoned mid-stream.
        with suppress(Exception):
            if self._lines is not None and hasattr(self._lines, "close"):
                self._lines.close()  # type: ignore[union-attr]

    def stats(self) -> StreamingReadStats:
        return StreamingReadStats(
            lines_read=self._lines_read,
            frames_yielded=self._frames,
            lines_dropped=self._dropped,
        )
