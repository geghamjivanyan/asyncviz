"""Speed change requests, results, and transition snapshots."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SpeedChangeRequest:
    """One speed-change intent."""

    request_id: int
    target_speed: float
    reason: str = ""
    requested_at_ns: int = field(default_factory=time.monotonic_ns)


@dataclass(frozen=True, slots=True)
class SpeedChangeResult:
    """Outcome of one speed-change call."""

    request_id: int
    requested_speed: float
    applied_speed: float
    """The speed actually installed on the clock. May differ from
    ``requested_speed`` under the ``clamp`` policy."""

    previous_speed: float
    coalesced: bool
    rejected: bool
    latency_ns: int
    clamped: bool
    """True when the request was outside the configured limits and
    the policy was ``clamp``."""

    error_detail: str = ""


@dataclass(frozen=True, slots=True)
class SpeedTransition:
    """Historical record — one entry per applied transition."""

    request_id: int
    previous_speed: float
    new_speed: float
    at_virtual_ns: int
    at_wall_ns: int
    latency_ns: int
    reason: str = ""
