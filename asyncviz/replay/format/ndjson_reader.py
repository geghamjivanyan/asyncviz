"""High-level NDJSON frame reader (single-file).

Mirror of :class:`NdjsonFrameWriter`. The reader is a thin wrapper
around :func:`iter_lines` + the recovering decoder, exposing a small
ergonomic surface for offline replay tooling: open it, iterate, get
typed frames back. Stats are accumulated under the hood so the
diagnostics page can show how many lines were dropped.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

from asyncviz.replay.format.ndjson_deserialization import (
    FrameDecodingError,
    decode_frame,
)
from asyncviz.replay.format.ndjson_frame import ReplayFrame
from asyncviz.replay.format.ndjson_observability import get_format_metrics
from asyncviz.replay.format.ndjson_recovery import FrameRecoveryRecord
from asyncviz.replay.format.ndjson_streaming import iter_lines


@dataclass(slots=True)
class NdjsonReadReport:
    """Stats from one streaming read."""

    lines_read: int = 0
    frames_yielded: int = 0
    discarded: list[FrameRecoveryRecord] = field(default_factory=list)

    @property
    def discarded_count(self) -> int:
        return len(self.discarded)


class NdjsonFrameReader:
    """Append-only NDJSON reader for a single recording file."""

    __slots__ = ("_path", "_report", "_strict")

    def __init__(self, path: Path, *, strict: bool = False) -> None:
        self._path = path
        self._strict = strict
        self._report = NdjsonReadReport()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def report(self) -> NdjsonReadReport:
        return self._report

    # ── lifecycle ─────────────────────────────────────────────────

    def __enter__(self) -> NdjsonFrameReader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # No persistent handle — :func:`iter_lines` owns it per pass.
        return None

    # ── iteration ─────────────────────────────────────────────────

    def __iter__(self) -> Iterator[ReplayFrame]:
        for line_no, line in enumerate(iter_lines(self._path), start=1):
            self._report.lines_read += 1
            try:
                frame = decode_frame(line)
            except FrameDecodingError as exc:
                self._report.discarded.append(
                    FrameRecoveryRecord(
                        line_number=line_no,
                        recovered=False,
                        reason=str(exc),
                    ),
                )
                get_format_metrics().record_malformed_frame()
                if self._strict:
                    raise
                continue
            self._report.frames_yielded += 1
            yield frame

    def materialize(self) -> list[ReplayFrame]:
        """Collect all frames into a list. Convenience for tests +
        offline tools; avoid for large recordings."""
        return list(self)

    def close(self) -> None:
        """No-op for symmetry — the reader holds no persistent state."""
        with suppress(Exception):
            pass
