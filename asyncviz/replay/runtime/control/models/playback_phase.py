"""Discrete coordination phases.

The phase the coordinator believes the engine is in — a strict
superset of :class:`PlaybackState` from the runtime layer, with
finer-grained transition states (``pausing``/``resuming``) so the
coordinator can express "we asked the engine to pause but it hasn't
acknowledged yet".

The phases are linearly ordered for the common forward flow:

    idle → playing → pausing → paused → resuming → playing

Plus the special states ``stepping`` (transient one-frame burst)
and ``stopped`` / ``failed`` (terminal).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlaybackPhase(StrEnum):
    """Coordination phase — what the coordinator thinks the engine
    is doing right now."""

    IDLE = "idle"
    """No playback loop attached / engine not started."""

    PLAYING = "playing"
    """Engine is actively dispatching frames."""

    PAUSING = "pausing"
    """Pause requested; waiting for the engine to reach a safe
    boundary + acknowledge."""

    PAUSED = "paused"
    """Engine has acknowledged pause + the playhead is frozen."""

    RESUMING = "resuming"
    """Resume requested; waiting for the engine to re-anchor the
    clock + restart dispatch."""

    STEPPING = "stepping"
    """One-frame burst in progress; engine returns to ``paused``
    after the step completes."""

    STOPPED = "stopped"
    """Terminal — engine has fully stopped (end-of-recording or
    explicit ``stop()``)."""

    FAILED = "failed"
    """Terminal — engine crashed; ``error_detail`` describes what
    happened."""


# Phases the engine is allowed to dispatch frames in.
_DISPATCHING_PHASES = frozenset({PlaybackPhase.PLAYING, PlaybackPhase.STEPPING})

# Phases that represent "paused for any reason".
_PAUSED_PHASES = frozenset({PlaybackPhase.PAUSED, PlaybackPhase.PAUSING})


@dataclass(frozen=True, slots=True)
class PlaybackPhaseSnapshot:
    """Read-only view of the coordinator's phase state."""

    phase: PlaybackPhase
    last_sequence: int
    last_monotonic_ns: int
    pause_request_id: int = 0
    """Monotonic counter so observers can correlate requests with
    transitions."""
    resume_request_id: int = 0
    error_detail: str = ""

    @property
    def is_dispatching(self) -> bool:
        return self.phase in _DISPATCHING_PHASES

    @property
    def is_paused(self) -> bool:
        return self.phase in _PAUSED_PHASES

    @property
    def is_terminal(self) -> bool:
        return self.phase in (PlaybackPhase.STOPPED, PlaybackPhase.FAILED)
