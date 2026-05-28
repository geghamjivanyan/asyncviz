"""Discrete states the seek coordinator moves through.

These are *coordinator-level* states — distinct from
:class:`PlaybackPhase` (which describes the engine). A seek
request walks the graph:

    idle → queued → reconstructing → applying → completed
                                              ↘ failed

A new request that arrives while one is in flight transitions the
in-flight request to ``cancelled`` (drop-oldest semantics).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SeekState(StrEnum):
    IDLE = "idle"
    """No seek in flight."""

    QUEUED = "queued"
    """Request accepted but reconstruction hasn't started yet."""

    RECONSTRUCTING = "reconstructing"
    """Engine is paused; reducer is replaying deltas."""

    APPLYING = "applying"
    """Reconstruction complete; state store + cursor + clock being
    swapped atomically."""

    COMPLETED = "completed"
    """Seek finished; coordinator is back to idle on the next
    request."""

    CANCELLED = "cancelled"
    """An incoming request superseded this one (coalescing)."""

    FAILED = "failed"
    """Reconstruction failed — error_detail describes what
    happened."""


@dataclass(frozen=True, slots=True)
class SeekStateSnapshot:
    """Immutable coordinator snapshot."""

    state: SeekState
    in_flight_request_id: int = 0
    target_sequence: int = 0
    last_completed_sequence: int = 0
    pending_count: int = 0
    error_detail: str = ""

    @property
    def is_in_flight(self) -> bool:
        return self.state in (
            SeekState.QUEUED,
            SeekState.RECONSTRUCTING,
            SeekState.APPLYING,
        )

    @property
    def is_terminal(self) -> bool:
        return self.state in (
            SeekState.COMPLETED,
            SeekState.CANCELLED,
            SeekState.FAILED,
        )
