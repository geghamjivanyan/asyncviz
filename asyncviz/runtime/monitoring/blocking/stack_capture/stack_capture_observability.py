"""Public snapshot envelope for the stack-capture engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_frames import (
    CapturedStack,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_metrics import (
    StackCaptureMetricsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_statistics import (
    StackCaptureStatisticsSnapshot,
)


@dataclass(frozen=True, slots=True)
class StackCaptureSnapshot:
    runtime_id: str
    state: str
    generated_at_monotonic_ns: int
    configuration: dict[str, object]
    statistics: StackCaptureStatisticsSnapshot
    metrics: StackCaptureMetricsSnapshot
    recent_captures: tuple[CapturedStack, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "state": self.state,
            "generated_at_monotonic_ns": self.generated_at_monotonic_ns,
            "configuration": self.configuration,
            "statistics": self.statistics.to_dict(),
            "metrics": self.metrics.to_dict(),
            "recent_captures": [c.to_dict() for c in self.recent_captures],
        }
