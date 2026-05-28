"""Seek-coordinator cursor.

Distinct from :class:`EngineCursor` (which tracks live playback)
and :class:`ReplayCursor` (which tracks loader read position). The
seek cursor is the coordinator's view of "where the next seek
should resume from" — used to compute relative offsets and to
re-bind the engine cursor after a seek completes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SeekCursor:
    """Immutable seek-coordinator position."""

    last_seek_sequence: int = 0
    last_seek_monotonic_ns: int = 0
    seeks_completed: int = 0
    last_request_id: int = 0

    @staticmethod
    def at_start() -> SeekCursor:
        return SeekCursor()

    def advance(
        self,
        *,
        sequence: int,
        monotonic_ns: int,
        request_id: int,
    ) -> SeekCursor:
        return SeekCursor(
            last_seek_sequence=sequence,
            last_seek_monotonic_ns=monotonic_ns,
            seeks_completed=self.seeks_completed + 1,
            last_request_id=request_id,
        )
