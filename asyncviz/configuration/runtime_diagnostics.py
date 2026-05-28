"""Diagnostics snapshot for the runtime-options layer.

Combines the resolved options + provenance + metrics + trace tail
into a single JSON-friendly view consumed by the diagnostics
endpoint + ``asyncviz doctor``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from asyncviz.configuration.runtime_metadata import ProvenanceMap
from asyncviz.configuration.runtime_observability import (
    ConfigurationMetricsSnapshot,
    get_configuration_metrics,
)
from asyncviz.configuration.runtime_resolution import ResolvedOptions
from asyncviz.configuration.runtime_serialization import (
    diff_options,
    options_to_dict,
)
from asyncviz.configuration.runtime_tracing import (
    ConfigurationTraceEntry,
    get_configuration_trace,
    is_configuration_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class ConfigurationDiagnosticsSnapshot:
    """Composed diagnostics view."""

    options: dict[str, Any]
    provenance: dict[str, dict[str, Any]]
    profile_name: str | None
    diff_from_defaults: dict[str, tuple[Any, Any]]
    metrics: ConfigurationMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[ConfigurationTraceEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "options": self.options,
            "provenance": self.provenance,
            "profile_name": self.profile_name,
            "diff_from_defaults": {
                key: list(values) for key, values in self.diff_from_defaults.items()
            },
            "metrics": asdict(self.metrics),
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [asdict(entry) for entry in self.recent_trace],
        }


def build_configuration_diagnostics(
    resolved: ResolvedOptions,
    *,
    tail: int = 16,
) -> ConfigurationDiagnosticsSnapshot:
    from asyncviz.configuration.runtime_options import default_runtime_options

    defaults = default_runtime_options()
    trace = get_configuration_trace()
    return ConfigurationDiagnosticsSnapshot(
        options=options_to_dict(resolved.options),
        provenance=resolved.provenance.to_dict(),
        profile_name=resolved.profile_name,
        diff_from_defaults=diff_options(defaults, resolved.options),
        metrics=get_configuration_metrics().snapshot(),
        trace_enabled=is_configuration_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
    )


def render_diagnostics_lines(snapshot: ConfigurationDiagnosticsSnapshot) -> list[str]:
    """Human-readable rendering used by ``asyncviz doctor``."""
    lines: list[str] = []
    lines.append(f"profile          {snapshot.profile_name or '<none>'}")
    lines.append(f"options diff     {len(snapshot.diff_from_defaults)} fields differ from defaults")
    for key, (default_value, current_value) in snapshot.diff_from_defaults.items():
        lines.append(f"  {key}: {default_value!r} -> {current_value!r}")
    return lines


def provenance_summary(provenance: ProvenanceMap) -> dict[str, int]:
    """Aggregate counts per source — useful for diagnostics dashboards."""
    counts: dict[str, int] = {}
    for _key, prov in provenance.items():
        counts[prov.source.name] = counts.get(prov.source.name, 0) + 1
    return counts
