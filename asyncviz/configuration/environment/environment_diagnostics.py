"""Diagnostics snapshot for the env loader."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from asyncviz.configuration.environment.environment_loader import LoaderResult
from asyncviz.configuration.environment.environment_observability import (
    EnvironmentMetricsSnapshot,
    get_environment_metrics,
)
from asyncviz.configuration.environment.environment_serialization import (
    loader_result_to_dict,
)
from asyncviz.configuration.environment.environment_tracing import (
    EnvironmentTraceEntry,
    get_environment_trace,
    is_environment_trace_enabled,
)
from asyncviz.configuration.environment.environment_validation import (
    EnvironmentValidationReport,
)


@dataclass(frozen=True, slots=True)
class EnvironmentDiagnosticsSnapshot:
    loader_result: dict[str, Any]
    validation: EnvironmentValidationReport
    metrics: EnvironmentMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[EnvironmentTraceEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "loader_result": self.loader_result,
            "validation": {
                "ok": self.validation.ok,
                "issues": [asdict(i) for i in self.validation.issues],
            },
            "metrics": asdict(self.metrics),
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [asdict(entry) for entry in self.recent_trace],
        }


def build_environment_diagnostics(
    result: LoaderResult,
    validation: EnvironmentValidationReport,
    *,
    tail: int = 16,
) -> EnvironmentDiagnosticsSnapshot:
    trace = get_environment_trace()
    return EnvironmentDiagnosticsSnapshot(
        loader_result=loader_result_to_dict(result),
        validation=validation,
        metrics=get_environment_metrics().snapshot(),
        trace_enabled=is_environment_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
    )
