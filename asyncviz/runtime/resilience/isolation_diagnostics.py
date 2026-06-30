"""One-call resilience diagnostics builder."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.resilience.failure_domain import FailureDomainSnapshot
from asyncviz.runtime.resilience.isolation_backpressure import (
    BackpressureSuggestion,
)
from asyncviz.runtime.resilience.isolation_configuration import EmergencyMode
from asyncviz.runtime.resilience.isolation_integrity import (
    IntegrityFinding,
)
from asyncviz.runtime.resilience.isolation_observability import (
    IsolationMetricsSnapshot,
)
from asyncviz.runtime.resilience.isolation_tracing import (
    IsolationTraceEntry,
    get_isolation_trace,
)
from asyncviz.runtime.resilience.recovery_supervisor import SupervisorSnapshot


@dataclass(frozen=True, slots=True)
class IsolationDiagnostics:
    mode: EmergencyMode
    metrics: IsolationMetricsSnapshot
    domains: tuple[FailureDomainSnapshot, ...]
    supervisors: tuple[SupervisorSnapshot, ...]
    suggestion: BackpressureSuggestion
    integrity_findings: tuple[IntegrityFinding, ...]
    trace: tuple[IsolationTraceEntry, ...]


@dataclass(frozen=True, slots=True)
class IsolationDiagnosticsInputs:
    mode: EmergencyMode
    metrics: IsolationMetricsSnapshot
    domains: tuple[FailureDomainSnapshot, ...]
    supervisors: tuple[SupervisorSnapshot, ...]
    suggestion: BackpressureSuggestion
    integrity_findings: tuple[IntegrityFinding, ...] = ()
    trace_limit: int = 64


def build_isolation_diagnostics(
    inputs: IsolationDiagnosticsInputs,
) -> IsolationDiagnostics:
    trace = get_isolation_trace()
    if inputs.trace_limit > 0 and len(trace) > inputs.trace_limit:
        trace = trace[-inputs.trace_limit :]
    return IsolationDiagnostics(
        mode=inputs.mode,
        metrics=inputs.metrics,
        domains=inputs.domains,
        supervisors=inputs.supervisors,
        suggestion=inputs.suggestion,
        integrity_findings=inputs.integrity_findings,
        trace=trace,
    )
