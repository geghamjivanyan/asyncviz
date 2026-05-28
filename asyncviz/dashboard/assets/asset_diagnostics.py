"""Composed diagnostics snapshot for the asset subsystem."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from asyncviz.dashboard.assets.asset_cache import (
    get_default_asset_cache,
)
from asyncviz.dashboard.assets.asset_export import summary_dict
from asyncviz.dashboard.assets.asset_observability import (
    AssetMetricsSnapshot,
    get_asset_metrics,
)
from asyncviz.dashboard.assets.asset_resolution import (
    ResolvedBundle,
    resolve_bundle,
)
from asyncviz.dashboard.assets.asset_tracing import (
    AssetTraceEntry,
    get_asset_trace,
    is_asset_trace_enabled,
)
from asyncviz.dashboard.assets.asset_validation import (
    AssetValidationReport,
    validate_published_bundle,
)


@dataclass(frozen=True, slots=True)
class AssetDiagnosticsSnapshot:
    bundle: dict[str, Any]
    manifest: dict[str, Any] | None
    validation: dict[str, Any]
    metrics: AssetMetricsSnapshot
    cache_entries: int
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[AssetTraceEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle": self.bundle,
            "manifest": self.manifest,
            "validation": self.validation,
            "metrics": asdict(self.metrics),
            "cache_entries": self.cache_entries,
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [asdict(entry) for entry in self.recent_trace],
        }


def _validation_to_dict(report: AssetValidationReport) -> dict[str, Any]:
    return {
        "ok": report.ok,
        "file_count": report.file_count,
        "total_bytes": report.total_bytes,
        "issues": [asdict(issue) for issue in report.issues],
    }


def _bundle_to_dict(bundle: ResolvedBundle) -> dict[str, Any]:
    return {
        "bundle_dir": str(bundle.bundle_dir),
        "index_path": str(bundle.index_path),
        "is_published": bundle.is_published,
        "has_manifest": bundle.manifest is not None,
    }


def build_asset_diagnostics(*, tail: int = 16) -> AssetDiagnosticsSnapshot:
    bundle = resolve_bundle()
    manifest_summary = summary_dict(bundle.manifest) if bundle.manifest else None
    validation = validate_published_bundle(bundle.bundle_dir)
    trace = get_asset_trace()
    return AssetDiagnosticsSnapshot(
        bundle=_bundle_to_dict(bundle),
        manifest=manifest_summary,
        validation=_validation_to_dict(validation),
        metrics=get_asset_metrics().snapshot(),
        cache_entries=len(get_default_asset_cache()),
        trace_enabled=is_asset_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
    )
