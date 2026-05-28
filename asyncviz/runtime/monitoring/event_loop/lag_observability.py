"""Public snapshot envelope for the lag monitor.

The dashboard's runtime snapshot composes a number of subsystem
snapshots; this module is the lag monitor's contribution. Differs from
:class:`LagDiagnosticsSnapshot` by being lean — no trace ring, no
debug detail. The wire payload is consumed by:

* /api/runtime/monitoring/lag                 (this snapshot)
* /api/runtime/snapshot                       (embedded)
* timeline overlays / live charts             (statistics field only)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.monitoring.event_loop.lag_measurement import LagMeasurement
from asyncviz.runtime.monitoring.event_loop.lag_metrics import LagMetricsSnapshot
from asyncviz.runtime.monitoring.event_loop.lag_state import LagMonitorState
from asyncviz.runtime.monitoring.event_loop.lag_statistics import LagStatisticsSnapshot


@dataclass(frozen=True, slots=True)
class LagSnapshot:
    """Lean lag-monitor view for dashboard consumption."""

    runtime_id: str
    state: LagMonitorState
    generated_at_monotonic_ns: int
    statistics: LagStatisticsSnapshot
    metrics: LagMetricsSnapshot
    last_measurement: LagMeasurement | None
    configuration: dict[str, object]

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "state": self.state.value,
            "generated_at_monotonic_ns": self.generated_at_monotonic_ns,
            "statistics": self.statistics.to_dict(),
            "metrics": self.metrics.to_dict(),
            "last_measurement": (
                self.last_measurement.to_dict() if self.last_measurement is not None else None
            ),
            "configuration": self.configuration,
        }
