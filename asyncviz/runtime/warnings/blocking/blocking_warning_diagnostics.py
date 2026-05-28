"""Debug-grade composite snapshot for the blocking warning emitter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.warnings.blocking.blocking_warning_backpressure import (
    WarningEmitterBackpressure,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_configuration import (
    BlockingWarningConfiguration,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_grouping import (
    WarningGroupRegistry,
    WarningGroupSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_metrics import (
    BlockingWarningMetrics,
    BlockingWarningMetricsSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_statistics import (
    BlockingWarningStatistics,
    BlockingWarningStatisticsSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_tracing import (
    BlockingWarningTracer,
    BlockingWarningTraceRecord,
)


@dataclass(frozen=True, slots=True)
class BlockingWarningDiagnosticsSnapshot:
    state: str
    configuration: dict[str, object]
    statistics: BlockingWarningStatisticsSnapshot
    metrics: BlockingWarningMetricsSnapshot
    active_groups: tuple[WarningGroupSnapshot, ...]
    recent_groups: tuple[WarningGroupSnapshot, ...]
    backpressure_pending: int
    backpressure_capacity: int
    backpressure_denied: int
    trace_enabled: bool
    trace_records: tuple[BlockingWarningTraceRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "configuration": self.configuration,
            "statistics": self.statistics.to_dict(),
            "metrics": self.metrics.to_dict(),
            "active_groups": [g.to_dict() for g in self.active_groups],
            "recent_groups": [g.to_dict() for g in self.recent_groups],
            "backpressure": {
                "pending": self.backpressure_pending,
                "capacity": self.backpressure_capacity,
                "denied": self.backpressure_denied,
            },
            "trace": {
                "enabled": self.trace_enabled,
                "records": [
                    {
                        "kind": r.kind,
                        "monotonic_ns": r.monotonic_ns,
                        "detail": r.detail,
                        "group_id": r.group_id,
                        "transition": r.transition,
                        "severity": r.severity,
                    }
                    for r in self.trace_records
                ],
            },
        }


class BlockingWarningDiagnostics:
    """Composes the diagnostics snapshot. Borrows references; owns no state."""

    __slots__ = (
        "_backpressure",
        "_configuration_getter",
        "_metrics",
        "_registry",
        "_state_getter",
        "_statistics",
        "_tracer",
    )

    def __init__(
        self,
        *,
        statistics: BlockingWarningStatistics,
        metrics: BlockingWarningMetrics,
        backpressure: WarningEmitterBackpressure,
        tracer: BlockingWarningTracer,
        registry: WarningGroupRegistry,
        state_getter: Callable[[], str],
        configuration_getter: Callable[[], BlockingWarningConfiguration],
    ) -> None:
        self._statistics = statistics
        self._metrics = metrics
        self._backpressure = backpressure
        self._tracer = tracer
        self._registry = registry
        self._state_getter = state_getter
        self._configuration_getter = configuration_getter

    def snapshot(self) -> BlockingWarningDiagnosticsSnapshot:
        return BlockingWarningDiagnosticsSnapshot(
            state=self._state_getter(),
            configuration=self._configuration_getter().to_dict(),
            statistics=self._statistics.snapshot(),
            metrics=self._metrics.snapshot(),
            active_groups=self._registry.active_snapshots(),
            recent_groups=self._registry.recent_snapshots(),
            backpressure_pending=self._backpressure.pending,
            backpressure_capacity=self._backpressure.capacity,
            backpressure_denied=self._backpressure.denied,
            trace_enabled=self._tracer.enabled,
            trace_records=self._tracer.snapshot(),
        )
