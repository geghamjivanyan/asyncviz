"""Engine cursor — the playback position of a running engine.

Distinct from :class:`asyncviz.replay.loading.ReplayCursor` (which
tracks read position over the on-disk recording). The engine cursor
additionally tracks *playback*-side coordinates: virtual time,
dispatched frame count, last checkpoint reference.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EngineCursor:
    """Immutable engine playback position."""

    last_sequence: int = 0
    last_monotonic_ns: int = 0
    frames_dispatched: int = 0
    last_virtual_ns: int = 0
    """Engine clock's virtual time when this cursor was captured.
    Snapshot/seek code uses this to rewind the clock atomically."""

    checkpoint_sequence: int = 0
    """Most recent checkpoint anchor (0 if none taken yet)."""

    @staticmethod
    def at_start() -> EngineCursor:
        return EngineCursor()

    def advance(
        self,
        *,
        sequence: int,
        monotonic_ns: int,
        virtual_ns: int,
    ) -> EngineCursor:
        return EngineCursor(
            last_sequence=sequence,
            last_monotonic_ns=monotonic_ns,
            frames_dispatched=self.frames_dispatched + 1,
            last_virtual_ns=virtual_ns,
            checkpoint_sequence=self.checkpoint_sequence,
        )

    def with_checkpoint(self, checkpoint_sequence: int) -> EngineCursor:
        return EngineCursor(
            last_sequence=self.last_sequence,
            last_monotonic_ns=self.last_monotonic_ns,
            frames_dispatched=self.frames_dispatched,
            last_virtual_ns=self.last_virtual_ns,
            checkpoint_sequence=checkpoint_sequence,
        )

    def jumped_to(
        self,
        *,
        sequence: int,
        monotonic_ns: int,
        virtual_ns: int,
    ) -> EngineCursor:
        """Used after a seek — preserves ``frames_dispatched`` so
        observability reports cumulative work rather than resetting
        on every scrub."""
        return EngineCursor(
            last_sequence=sequence,
            last_monotonic_ns=monotonic_ns,
            frames_dispatched=self.frames_dispatched,
            last_virtual_ns=virtual_ns,
            checkpoint_sequence=self.checkpoint_sequence,
        )
