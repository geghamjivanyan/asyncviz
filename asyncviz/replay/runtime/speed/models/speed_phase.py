"""Discrete phases the speed coordinator moves through.

A speed change walks:

    idle → applying → applied
                  ↘ coalesced
                  ↘ rejected

with terminal ``applied``/``coalesced``/``rejected`` snapshots
surfaced through subscribers so UIs can render transition state
(loading spinners, error toasts) coherently.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SpeedPhase(StrEnum):
    IDLE = "idle"
    """No transition in flight."""

    APPLYING = "applying"
    """Clock + scheduler being re-anchored under the request."""

    APPLIED = "applied"
    """Last transition completed; coordinator is back to idle on the
    next request."""

    COALESCED = "coalesced"
    """A newer request superseded this one before it ran (drop-oldest)."""

    REJECTED = "rejected"
    """The request was invalid (out of range, NaN, ≤ 0) and the
    invalid-speed policy is ``reject``."""


_TERMINAL_PHASES = frozenset(
    {SpeedPhase.APPLIED, SpeedPhase.COALESCED, SpeedPhase.REJECTED},
)


@dataclass(frozen=True, slots=True)
class SpeedPhaseSnapshot:
    """Immutable coordinator phase snapshot."""

    phase: SpeedPhase
    in_flight_request_id: int = 0
    target_speed: float = 0.0
    current_speed: float = 0.0
    last_completed_speed: float = 0.0
    error_detail: str = ""

    @property
    def is_in_flight(self) -> bool:
        return self.phase == SpeedPhase.APPLYING

    @property
    def is_terminal(self) -> bool:
        return self.phase in _TERMINAL_PHASES
