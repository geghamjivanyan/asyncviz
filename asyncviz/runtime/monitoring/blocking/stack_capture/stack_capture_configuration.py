"""Frozen knobs for the stack-capture engine.

Composes the policy + filter + limits + emission/lifecycle flags into
one immutable value type. The engine accepts a fresh instance on
:meth:`reconfigure` and rebuilds the sub-components that own
configuration-shaped state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from asyncviz.runtime.monitoring.blocking.blocking_classifier import BlockingSeverity
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_filters import (
    FilterPolicy,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_limits import (
    StackCaptureLimits,
)


@dataclass(frozen=True, slots=True)
class StackCaptureConfiguration:
    """All stack-capture knobs in one frozen value type.

    Defaults are tuned for:
      * minimal overhead — only CRITICAL+ severities capture.
      * 3 captures per window — first violation + escalation + freeze.
      * 16 KB max payload — large enough for a 50-frame trace with
        full source context, small enough to ride the bus comfortably.
    """

    enabled: bool = True
    min_severity: BlockingSeverity = BlockingSeverity.CRITICAL
    always_capture_severity: BlockingSeverity = BlockingSeverity.FREEZE
    max_captures_per_window: int = 3
    capture_outside_windows: bool = True
    capture_warning: bool = False
    limits: StackCaptureLimits = field(default_factory=StackCaptureLimits)
    filters: FilterPolicy = field(default_factory=FilterPolicy.default)
    recent_capacity: int = 32
    top_frame_limit: int = 10
    max_pending_events: int = 256
    emit_events: bool = True
    capture_task_metadata: bool = True
    trace_enabled: bool = False

    def __post_init__(self) -> None:
        if self.max_captures_per_window < 1:
            raise ValueError(
                f"max_captures_per_window must be >= 1 (got {self.max_captures_per_window})"
            )
        if self.recent_capacity <= 0:
            raise ValueError(f"recent_capacity must be > 0 (got {self.recent_capacity})")
        if self.top_frame_limit <= 0:
            raise ValueError(f"top_frame_limit must be > 0 (got {self.top_frame_limit})")
        if self.max_pending_events < 0:
            raise ValueError(f"max_pending_events must be >= 0 (got {self.max_pending_events})")

    @classmethod
    def default(cls) -> StackCaptureConfiguration:
        return cls()

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "min_severity": self.min_severity.name,
            "always_capture_severity": self.always_capture_severity.name,
            "max_captures_per_window": self.max_captures_per_window,
            "capture_outside_windows": self.capture_outside_windows,
            "capture_warning": self.capture_warning,
            "limits": self.limits.to_dict(),
            "filters": self.filters.to_dict(),
            "recent_capacity": self.recent_capacity,
            "top_frame_limit": self.top_frame_limit,
            "max_pending_events": self.max_pending_events,
            "emit_events": self.emit_events,
            "capture_task_metadata": self.capture_task_metadata,
            "trace_enabled": self.trace_enabled,
        }
