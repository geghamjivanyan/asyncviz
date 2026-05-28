"""Public snapshot envelope for the blocking warning emitter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.warnings.blocking.blocking_warning_grouping import (
    WarningGroupSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_metrics import (
    BlockingWarningMetricsSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_statistics import (
    BlockingWarningStatisticsSnapshot,
)


@dataclass(frozen=True, slots=True)
class BlockingWarningEmitterSnapshot:
    runtime_id: str
    state: str
    generated_at_monotonic_ns: int
    configuration: dict[str, object]
    statistics: BlockingWarningStatisticsSnapshot
    metrics: BlockingWarningMetricsSnapshot
    active_groups: tuple[WarningGroupSnapshot, ...]
    recent_groups: tuple[WarningGroupSnapshot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "state": self.state,
            "generated_at_monotonic_ns": self.generated_at_monotonic_ns,
            "configuration": self.configuration,
            "statistics": self.statistics.to_dict(),
            "metrics": self.metrics.to_dict(),
            "active_groups": [g.to_dict() for g in self.active_groups],
            "recent_groups": [g.to_dict() for g in self.recent_groups],
        }
