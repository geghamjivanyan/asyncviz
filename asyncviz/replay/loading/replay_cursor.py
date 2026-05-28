"""Replay cursor — current position inside a recording.

A cursor is a *value object*: every advance produces a new cursor
rather than mutating the previous one, so callers can capture
positions to resume from later (replay scrubbing, distributed
checkpoints) without worrying about aliasing.

The cursor's three coordinates cover what consumers need to ask:

* ``last_sequence`` — the highest sequence number observed so far.
  Replay engines use this to decide whether to apply a frame.
* ``chunk_index`` — which manifest chunk the cursor is reading from.
  Useful for seeking + diagnostics.
* ``frames_consumed`` — how many frames the cursor has yielded since
  the loader opened. Distinct from ``last_sequence`` because dropped
  frames create gaps in sequence space but not in consumption.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReplayCursor:
    """Immutable position inside a replay session."""

    chunk_index: int = 0
    """1-based manifest chunk index the cursor is currently inside,
    or 0 if no chunk has been opened yet."""

    last_sequence: int = 0
    """Highest sequence number the cursor has yielded so far. Zero
    means the cursor hasn't yielded any frames."""

    frames_consumed: int = 0
    """Total frames yielded since the loader opened."""

    last_monotonic_ns: int = 0
    """Monotonic timestamp of the most recently-yielded frame. Useful
    for timestamp seeking + replay-rate tracking."""

    snapshot_index: int = -1
    """Most recent snapshot index applied (-1 if none)."""

    @staticmethod
    def at_start() -> ReplayCursor:
        return ReplayCursor()

    def advance(
        self,
        *,
        chunk_index: int,
        sequence: int,
        monotonic_ns: int,
    ) -> ReplayCursor:
        """Return a new cursor advanced past one yielded frame."""
        return ReplayCursor(
            chunk_index=chunk_index,
            last_sequence=sequence,
            frames_consumed=self.frames_consumed + 1,
            last_monotonic_ns=monotonic_ns,
            snapshot_index=self.snapshot_index,
        )

    def with_snapshot(self, snapshot_index: int) -> ReplayCursor:
        return ReplayCursor(
            chunk_index=self.chunk_index,
            last_sequence=self.last_sequence,
            frames_consumed=self.frames_consumed,
            last_monotonic_ns=self.last_monotonic_ns,
            snapshot_index=snapshot_index,
        )

    def reset(self) -> ReplayCursor:
        return ReplayCursor()
