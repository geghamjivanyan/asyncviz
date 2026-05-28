"""Overload state machine.

Four discrete states the controller moves through. Transitions are
gated by hysteresis bands + a dwell time so the system doesn't
flap on transient spikes.

    NORMAL    → ELEVATED   → OVERLOAD  → EMERGENCY
       ↑           ↑            ↑           ↓
       └───────────┴────────────┴───────────┘
                  (dwell-time gated recovery)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class OverloadState(IntEnum):
    """Discrete pressure tiers — *higher value = more severe*."""

    NORMAL = 0
    """No pressure intervention — events flow through unchanged."""

    ELEVATED = 1
    """Mild pressure — adaptive sampling tightens, low-priority
    work defers."""

    OVERLOAD = 2
    """Sustained pressure — bounded queues drop oldest, websocket
    sampler engages, recorder may flush more aggressively."""

    EMERGENCY = 3
    """Critical pressure — emergency action triggered (shed /
    disconnect slow clients / halt production)."""


@dataclass(frozen=True, slots=True)
class OverloadSnapshot:
    """Read-only view of the controller's current state."""

    state: OverloadState
    pressure_ratio: float
    """Current smoothed pressure as a fraction of capacity (0..1+)."""

    raw_pressure: int
    """Most recent raw pressure reading (queue depth, event rate, …)."""

    last_transition_at_ns: int = 0
    transitions: int = 0
    emergency_actions_taken: int = 0
    last_action_detail: str = ""

    @property
    def normal(self) -> bool:
        return self.state == OverloadState.NORMAL

    @property
    def under_pressure(self) -> bool:
        return self.state >= OverloadState.ELEVATED

    @property
    def overloaded(self) -> bool:
        return self.state >= OverloadState.OVERLOAD

    @property
    def emergency(self) -> bool:
        return self.state == OverloadState.EMERGENCY
