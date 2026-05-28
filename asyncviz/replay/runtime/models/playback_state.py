"""Playback state machine values.

States the engine moves through and a frozen snapshot of all the
public knobs callers care about. Both are pure value types — the
engine is free to inspect/return them without leaking internal
locks or async state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlaybackState(StrEnum):
    """Discrete states the playback loop can occupy."""

    IDLE = "idle"
    """No playback session in progress."""

    PLAYING = "playing"
    """Loop is dispatching frames on schedule."""

    PAUSED = "paused"
    """Loop is suspended; cursor frozen."""

    SEEKING = "seeking"
    """Loop is mid-seek; state reconstruction in progress."""

    STOPPED = "stopped"
    """Loop terminated (either by stop() or end-of-recording)."""

    FAILED = "failed"
    """Loop crashed; ``error_detail`` describes what happened."""


@dataclass(frozen=True, slots=True)
class PlaybackSnapshot:
    """Immutable snapshot of every playback knob a caller can see."""

    state: PlaybackState
    speed: float
    last_sequence: int
    last_monotonic_ns: int
    frames_dispatched: int
    queue_depth: int
    paused: bool
    error_detail: str = ""
