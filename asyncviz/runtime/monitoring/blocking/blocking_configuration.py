"""Detector configuration — all knobs in one frozen value type.

The detector reads this at construction. Atomic reconfiguration goes
through :meth:`BlockingThresholdDetector.reconfigure`, which rebuilds
the sub-engines that own configuration-shaped state (windows /
cooldowns / escalation policy) and swaps them atomically.

Defaults compose with the lag monitor's defaults: a sample interval of
200ms plus an escalation threshold of 5 means "5 consecutive WARNINGs
over ~1s pressure is enough to escalate to CRITICAL."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from asyncviz.runtime.monitoring.blocking.blocking_cooldown import BlockingCooldownPolicy
from asyncviz.runtime.monitoring.blocking.blocking_thresholds import BlockingThresholdPolicy


@dataclass(frozen=True, slots=True)
class BlockingDetectorConfiguration:
    """Frozen knobs for the blocking detector.

    Fields:

    * ``thresholds``                — :class:`BlockingThresholdPolicy`.
    * ``cooldown_warning_ns``       — WARNING-event suppression window.
    * ``cooldown_critical_ns``      — CRITICAL-event suppression window.
    * ``cooldown_freeze_ns``        — FREEZE-event suppression window.
    * ``window_history_capacity``   — closed-window ring size.
    * ``max_pending_events``        — backpressure cap on emission.
    * ``emit_violation_events``     — emit one event per accepted
      violation (suppressed by cooldowns).
    * ``emit_window_events``        — emit on window open/close/extend.
    * ``emit_escalation_events``    — emit on severity escalation.
    * ``trace_enabled``             — debug ring; off in production.
    """

    thresholds: BlockingThresholdPolicy = field(default_factory=BlockingThresholdPolicy)
    cooldown_warning_ns: int = BlockingCooldownPolicy.DEFAULT_WARNING_COOLDOWN_NS
    cooldown_critical_ns: int = BlockingCooldownPolicy.DEFAULT_CRITICAL_COOLDOWN_NS
    cooldown_freeze_ns: int = BlockingCooldownPolicy.DEFAULT_FREEZE_COOLDOWN_NS
    window_history_capacity: int = 64
    max_pending_events: int = 512
    emit_violation_events: bool = True
    emit_window_events: bool = True
    emit_escalation_events: bool = True
    trace_enabled: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("cooldown_warning_ns", self.cooldown_warning_ns),
            ("cooldown_critical_ns", self.cooldown_critical_ns),
            ("cooldown_freeze_ns", self.cooldown_freeze_ns),
            ("max_pending_events", self.max_pending_events),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0 (got {value})")
        if self.window_history_capacity <= 0:
            raise ValueError(
                f"window_history_capacity must be > 0 (got {self.window_history_capacity})"
            )

    @classmethod
    def default(cls) -> BlockingDetectorConfiguration:
        return cls()

    def to_dict(self) -> dict[str, object]:
        return {
            "thresholds": self.thresholds.to_dict(),
            "cooldown_warning_ns": self.cooldown_warning_ns,
            "cooldown_critical_ns": self.cooldown_critical_ns,
            "cooldown_freeze_ns": self.cooldown_freeze_ns,
            "window_history_capacity": self.window_history_capacity,
            "max_pending_events": self.max_pending_events,
            "emit_violation_events": self.emit_violation_events,
            "emit_window_events": self.emit_window_events,
            "emit_escalation_events": self.emit_escalation_events,
            "trace_enabled": self.trace_enabled,
        }
