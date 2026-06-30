"""Malformed-frame isolation for replay streams.

The recording layer at :mod:`asyncviz.replay.recording.recording_integrity`
already handles *file-level* recovery (truncating a partial trailing
line). This module handles *frame-level* recovery during decode: a
single corrupt line in the middle of a stream shouldn't kill the
whole replay.

The :class:`RecoveringDecoder` wraps an iterable of raw lines + emits
:class:`RecoveryOutcome` records so the caller knows exactly what was
preserved and what was discarded.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from asyncviz.replay.format.ndjson_deserialization import (
    FrameDecodingError,
    decode_frame,
)
from asyncviz.replay.format.ndjson_frame import ReplayFrame
from asyncviz.replay.format.ndjson_observability import get_format_metrics
from asyncviz.replay.format.ndjson_tracing import record_ndjson_trace


@dataclass(frozen=True, slots=True)
class FrameRecoveryRecord:
    """One entry for an attempted decode."""

    line_number: int
    recovered: bool
    reason: str = ""


@dataclass(slots=True)
class RecoveryOutcome:
    """Aggregate result of a recovering decode pass."""

    recovered_frames: list[ReplayFrame] = field(default_factory=list)
    discarded: list[FrameRecoveryRecord] = field(default_factory=list)
    """All malformed-line records, in the order they were encountered."""

    @property
    def recovered_count(self) -> int:
        return len(self.recovered_frames)

    @property
    def discarded_count(self) -> int:
        return len(self.discarded)


def recover_frames(lines: Iterable[str | bytes]) -> RecoveryOutcome:
    """Decode every line; skip malformed ones; return what survived
    + a structured record of what didn't."""
    outcome = RecoveryOutcome()
    for line_number, raw in enumerate(lines, start=1):
        try:
            frame = decode_frame(raw)
        except FrameDecodingError as exc:
            outcome.discarded.append(
                FrameRecoveryRecord(
                    line_number=line_number,
                    recovered=False,
                    reason=str(exc),
                ),
            )
            record_ndjson_trace("recovery-discarded", f"line={line_number}")
            continue
        outcome.recovered_frames.append(frame)
        record_ndjson_trace("recovery-recovered", f"line={line_number} seq={frame.sequence}")
    return outcome


class RecoveringDecoder:
    """Iterator-style wrapper. Use when you don't want to materialize
    the whole stream into a list — the inner generator yields only
    successfully-decoded frames, while :attr:`discarded` accumulates
    malformed-line records as a side-channel."""

    __slots__ = ("_discarded", "_lines", "_recovered")

    def __init__(self, lines: Iterable[str | bytes]) -> None:
        self._lines = lines
        self._discarded: list[FrameRecoveryRecord] = []
        self._recovered = 0

    @property
    def discarded(self) -> tuple[FrameRecoveryRecord, ...]:
        return tuple(self._discarded)

    @property
    def recovered_count(self) -> int:
        return self._recovered

    def __iter__(self) -> Iterator[ReplayFrame]:
        for line_number, raw in enumerate(self._lines, start=1):
            try:
                frame = decode_frame(raw)
            except FrameDecodingError as exc:
                self._discarded.append(
                    FrameRecoveryRecord(
                        line_number=line_number,
                        recovered=False,
                        reason=str(exc),
                    ),
                )
                get_format_metrics().record_malformed_frame()
                record_ndjson_trace("recovery-discarded", f"line={line_number}")
                continue
            self._recovered += 1
            yield frame
