"""Per-session heartbeat tracking.

The gateway pings every session at a configurable interval. Sessions that
miss a configurable number of consecutive heartbeats are considered
stale and the gateway disconnects them. Lightweight — the heartbeat is
just another ``heartbeat`` envelope on the existing protocol; this
module owns the scheduling + miss-counting state.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Default heartbeat interval in seconds. Aligns with the existing
#: dashboard lifespan default — tests can override per-instance.
DEFAULT_HEARTBEAT_INTERVAL_SECONDS: float = 5.0
DEFAULT_MAX_MISSED_HEARTBEATS: int = 3


@dataclass(frozen=True, slots=True)
class HeartbeatPolicy:
    """Configuration knobs for the gateway's heartbeat loop."""

    interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    max_missed: int = DEFAULT_MAX_MISSED_HEARTBEATS

    @property
    def interval_ns(self) -> int:
        return int(self.interval_seconds * 1_000_000_000)

    def is_stale(self, *, now_monotonic_ns: int, last_activity_monotonic_ns: int) -> bool:
        """``True`` iff a session has been idle for ``max_missed`` intervals."""
        threshold_ns = self.interval_ns * self.max_missed
        return (now_monotonic_ns - last_activity_monotonic_ns) >= threshold_ns
