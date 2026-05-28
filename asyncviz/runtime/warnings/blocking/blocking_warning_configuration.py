"""Frozen knobs for the blocking warning emitter.

Composes the policy + dedup + lifecycle / safety / observability flags
into one immutable value type. The emitter accepts a fresh instance on
:meth:`reconfigure` and rebuilds the sub-engines that own
configuration-shaped state.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.monitoring.blocking import BlockingSeverity


@dataclass(frozen=True, slots=True)
class BlockingWarningConfiguration:
    """All emitter knobs in one frozen value type.

    Defaults:
      * surface CRITICAL+ violations only.
      * 250 ms cooldown between ``active`` refreshes for the same group.
      * 16-entry escalation history per group.
      * 30 s post-recovery TTL before a group can expire.
      * 64-group recent ring for the snapshot endpoint.
    """

    enabled: bool = True
    min_severity: BlockingSeverity = BlockingSeverity.CRITICAL
    include_no_window: bool = False
    escalations_only: bool = False
    opened_cooldown_ns: int = 0
    escalated_cooldown_ns: int = 0
    active_cooldown_ns: int = 250_000_000
    recovered_cooldown_ns: int = 0
    expired_cooldown_ns: int = 0
    recent_capacity: int = 64
    top_coroutine_limit: int = 5
    expiration_ttl_ns: int = 30_000_000_000  # 30 s default
    max_pending_events: int = 256
    emit_events: bool = True
    trace_enabled: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("opened_cooldown_ns", self.opened_cooldown_ns),
            ("escalated_cooldown_ns", self.escalated_cooldown_ns),
            ("active_cooldown_ns", self.active_cooldown_ns),
            ("recovered_cooldown_ns", self.recovered_cooldown_ns),
            ("expired_cooldown_ns", self.expired_cooldown_ns),
            ("expiration_ttl_ns", self.expiration_ttl_ns),
            ("max_pending_events", self.max_pending_events),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0 (got {value})")
        if self.recent_capacity <= 0:
            raise ValueError(f"recent_capacity must be > 0 (got {self.recent_capacity})")
        if self.top_coroutine_limit <= 0:
            raise ValueError(f"top_coroutine_limit must be > 0 (got {self.top_coroutine_limit})")

    @classmethod
    def default(cls) -> BlockingWarningConfiguration:
        return cls()

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "min_severity": self.min_severity.name,
            "include_no_window": self.include_no_window,
            "escalations_only": self.escalations_only,
            "opened_cooldown_ns": self.opened_cooldown_ns,
            "escalated_cooldown_ns": self.escalated_cooldown_ns,
            "active_cooldown_ns": self.active_cooldown_ns,
            "recovered_cooldown_ns": self.recovered_cooldown_ns,
            "expired_cooldown_ns": self.expired_cooldown_ns,
            "recent_capacity": self.recent_capacity,
            "top_coroutine_limit": self.top_coroutine_limit,
            "expiration_ttl_ns": self.expiration_ttl_ns,
            "max_pending_events": self.max_pending_events,
            "emit_events": self.emit_events,
            "trace_enabled": self.trace_enabled,
        }
