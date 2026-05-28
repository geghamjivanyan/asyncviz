"""Public snapshot envelope for the blocking detector.

Mirrors :class:`LagSnapshot` but with blocking-specific fields. The
dashboard consumes :meth:`BlockingThresholdDetector.snapshot` to power
the diagnostics panel + timeline overlays. Diagnostics-grade detail
(trace ring) lives on :class:`BlockingDiagnosticsSnapshot`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.monitoring.blocking.blocking_metrics import BlockingMetricsSnapshot
from asyncviz.runtime.monitoring.blocking.blocking_state import BlockingDetectorState
from asyncviz.runtime.monitoring.blocking.blocking_statistics import (
    BlockingStatisticsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.blocking_windows import BlockingWindowSnapshot


@dataclass(frozen=True, slots=True)
class BlockingSnapshot:
    runtime_id: str
    state: BlockingDetectorState
    generated_at_monotonic_ns: int
    configuration: dict[str, object]
    statistics: BlockingStatisticsSnapshot
    metrics: BlockingMetricsSnapshot
    active_window: BlockingWindowSnapshot | None
    recent_windows: tuple[BlockingWindowSnapshot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "state": self.state.value,
            "generated_at_monotonic_ns": self.generated_at_monotonic_ns,
            "configuration": self.configuration,
            "statistics": self.statistics.to_dict(),
            "metrics": self.metrics.to_dict(),
            "active_window": (
                self.active_window.to_dict() if self.active_window is not None else None
            ),
            "recent_windows": [w.to_dict() for w in self.recent_windows],
        }
