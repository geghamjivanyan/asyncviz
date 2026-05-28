"""One-call stress diagnostics builder.

Mirrors every other layer: a frozen snapshot of every sub-system at
a single instant.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.stress.scalability_reports.scalability_report import ScalabilityReport
from asyncviz.stress.stress_observability import (
    StressMetricsSnapshot,
    get_stress_metrics_snapshot,
)
from asyncviz.stress.stress_tracing import (
    StressTraceEntry,
    get_stress_trace,
)


@dataclass(frozen=True, slots=True)
class StressDiagnostics:
    metrics: StressMetricsSnapshot
    report: ScalabilityReport | None
    trace: tuple[StressTraceEntry, ...]


def build_stress_diagnostics(
    *,
    report: ScalabilityReport | None = None,
    trace_limit: int = 64,
) -> StressDiagnostics:
    """Build a structured diagnostics snapshot."""
    trace = get_stress_trace()
    if trace_limit > 0 and len(trace) > trace_limit:
        trace = trace[-trace_limit:]
    return StressDiagnostics(
        metrics=get_stress_metrics_snapshot(),
        report=report,
        trace=trace,
    )
