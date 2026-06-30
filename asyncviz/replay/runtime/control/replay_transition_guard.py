"""Static transition validator.

The coordinator's phase graph is small enough to enumerate. The
guard owns the legal set + provides one ``check`` function. Strict
mode raises on violation; otherwise the coordinator records the
attempt + leaves state unchanged.

Legal transitions:

    idle      → playing, stopped, failed
    playing   → pausing, paused (direct), stopped, failed, stepping
    pausing   → paused, playing (cancel), failed
    paused    → resuming, stepping, playing (direct), stopped, failed
    resuming  → playing, paused (cancel), failed
    stepping  → paused, playing, failed
    stopped   → idle (reset)
    failed    → idle (reset)
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.control.models.playback_phase import PlaybackPhase

_LEGAL_TRANSITIONS: dict[PlaybackPhase, frozenset[PlaybackPhase]] = {
    PlaybackPhase.IDLE: frozenset(
        {PlaybackPhase.PLAYING, PlaybackPhase.STOPPED, PlaybackPhase.FAILED},
    ),
    PlaybackPhase.PLAYING: frozenset(
        {
            PlaybackPhase.PAUSING,
            PlaybackPhase.PAUSED,
            PlaybackPhase.STEPPING,
            PlaybackPhase.STOPPED,
            PlaybackPhase.FAILED,
        },
    ),
    PlaybackPhase.PAUSING: frozenset(
        {
            PlaybackPhase.PAUSED,
            PlaybackPhase.PLAYING,
            PlaybackPhase.FAILED,
            PlaybackPhase.STOPPED,
        },
    ),
    PlaybackPhase.PAUSED: frozenset(
        {
            PlaybackPhase.RESUMING,
            PlaybackPhase.STEPPING,
            PlaybackPhase.PLAYING,
            PlaybackPhase.STOPPED,
            PlaybackPhase.FAILED,
        },
    ),
    PlaybackPhase.RESUMING: frozenset(
        {
            PlaybackPhase.PLAYING,
            PlaybackPhase.PAUSED,
            PlaybackPhase.FAILED,
            PlaybackPhase.STOPPED,
        },
    ),
    PlaybackPhase.STEPPING: frozenset(
        {
            PlaybackPhase.PAUSED,
            PlaybackPhase.PLAYING,
            PlaybackPhase.FAILED,
            PlaybackPhase.STOPPED,
        },
    ),
    PlaybackPhase.STOPPED: frozenset({PlaybackPhase.IDLE}),
    PlaybackPhase.FAILED: frozenset({PlaybackPhase.IDLE}),
}


class IllegalTransitionError(ValueError):
    """Raised when an illegal transition is attempted under strict
    mode."""


@dataclass(frozen=True, slots=True)
class TransitionVerdict:
    """Result of a ``check`` call."""

    allowed: bool
    previous: PlaybackPhase
    next: PlaybackPhase
    reason: str = ""

    def raise_if_illegal(self) -> None:
        if not self.allowed:
            raise IllegalTransitionError(
                f"illegal transition {self.previous} → {self.next}: {self.reason}",
            )


def check_transition(
    previous: PlaybackPhase,
    next_phase: PlaybackPhase,
) -> TransitionVerdict:
    """Pure check — does NOT mutate any state."""
    if previous == next_phase:
        return TransitionVerdict(
            allowed=True,
            previous=previous,
            next=next_phase,
            reason="no-op",
        )
    allowed = next_phase in _LEGAL_TRANSITIONS.get(previous, frozenset())
    return TransitionVerdict(
        allowed=allowed,
        previous=previous,
        next=next_phase,
        reason="" if allowed else f"{previous} cannot transition to {next_phase}",
    )


def legal_next_phases(previous: PlaybackPhase) -> frozenset[PlaybackPhase]:
    """Return the set of phases ``previous`` can transition into."""
    return _LEGAL_TRANSITIONS.get(previous, frozenset())
