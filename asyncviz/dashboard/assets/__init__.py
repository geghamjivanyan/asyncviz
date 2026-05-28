"""Canonical frontend-asset publishing + validation surface.

The module owns the *publish* pipeline (build → embed → manifest →
validate) and the runtime asset-resolution surface (which file
should the dashboard serve?). It sits next to
:mod:`asyncviz.packaging` — the packaging module owns the
artifact-side validation (wheel/sdist contents); this module owns
the dashboard-side state.
"""

from asyncviz.dashboard.assets.asset_build import (
    FrontendBuilder,
    FrontendBuildOutcome,
    NoopBuilder,
    NpmFrontendBuilder,
)
from asyncviz.dashboard.assets.asset_cache import (
    AssetCache,
    CachedAsset,
    get_default_asset_cache,
    reset_default_asset_cache,
)
from asyncviz.dashboard.assets.asset_diagnostics import (
    AssetDiagnosticsSnapshot,
    build_asset_diagnostics,
)
from asyncviz.dashboard.assets.asset_export import (
    manifest_to_json,
    summary_dict,
)
from asyncviz.dashboard.assets.asset_integrity import (
    atomic_write_text,
    content_type_for,
    sha256_file,
)
from asyncviz.dashboard.assets.asset_layout import (
    ASSET_MANIFEST_FILENAME,
    ASSET_MANIFEST_VERSION,
    ASSETS_DIRECTORY,
    IGNORED_FILES,
    INDEX_HTML,
    REQUIRED_FILES,
    VITE_MANIFEST_FILENAME,
    asset_relative_path,
)
from asyncviz.dashboard.assets.asset_manifest import (
    build_manifest_model,
    load_manifest,
    manifest_from_dict,
    manifest_to_dict,
    write_manifest,
)
from asyncviz.dashboard.assets.asset_metadata import (
    AssetManifestModel,
    AssetMetadata,
    AssetRole,
)
from asyncviz.dashboard.assets.asset_observability import (
    AssetMetricsSnapshot,
    get_asset_metrics,
    reset_asset_metrics,
)
from asyncviz.dashboard.assets.asset_packaging import (
    copy_bundle,
    wipe_published_bundle,
)
from asyncviz.dashboard.assets.asset_packaging_inspect import (
    ArchiveKind,
    WheelAssetEntry,
    WheelAssetReport,
    inspect_sdist,
    inspect_wheel,
)
from asyncviz.dashboard.assets.asset_publisher import (
    FrontendAssetPublisher,
    PublishResult,
)
from asyncviz.dashboard.assets.asset_registry import collect_assets
from asyncviz.dashboard.assets.asset_resolution import (
    ResolvedBundle,
    reset_resolution_cache,
    resolve_asset_path,
    resolve_bundle,
)
from asyncviz.dashboard.assets.asset_tracing import (
    AssetTraceEntry,
    AssetTraceKind,
    clear_asset_trace,
    get_asset_trace,
    is_asset_trace_enabled,
    record_asset_trace,
    set_asset_trace_enabled,
)
from asyncviz.dashboard.assets.asset_validation import (
    AssetValidationIssue,
    AssetValidationReport,
    validate_published_bundle,
)
from asyncviz.dashboard.assets.asset_versioning import (
    current_build_timestamp,
    read_frontend_version,
    read_git_commit,
)

__all__ = [
    "ASSETS_DIRECTORY",
    "ASSET_MANIFEST_FILENAME",
    "ASSET_MANIFEST_VERSION",
    "IGNORED_FILES",
    "INDEX_HTML",
    "REQUIRED_FILES",
    "VITE_MANIFEST_FILENAME",
    "ArchiveKind",
    "AssetCache",
    "AssetDiagnosticsSnapshot",
    "AssetManifestModel",
    "AssetMetadata",
    "AssetMetricsSnapshot",
    "AssetRole",
    "AssetTraceEntry",
    "AssetTraceKind",
    "AssetValidationIssue",
    "AssetValidationReport",
    "CachedAsset",
    "FrontendAssetPublisher",
    "FrontendBuildOutcome",
    "FrontendBuilder",
    "NoopBuilder",
    "NpmFrontendBuilder",
    "PublishResult",
    "ResolvedBundle",
    "WheelAssetEntry",
    "WheelAssetReport",
    "asset_relative_path",
    "atomic_write_text",
    "build_asset_diagnostics",
    "build_manifest_model",
    "clear_asset_trace",
    "collect_assets",
    "content_type_for",
    "copy_bundle",
    "current_build_timestamp",
    "get_asset_metrics",
    "get_asset_trace",
    "get_default_asset_cache",
    "inspect_sdist",
    "inspect_wheel",
    "is_asset_trace_enabled",
    "load_manifest",
    "manifest_from_dict",
    "manifest_to_dict",
    "manifest_to_json",
    "read_frontend_version",
    "read_git_commit",
    "record_asset_trace",
    "reset_asset_metrics",
    "reset_default_asset_cache",
    "reset_resolution_cache",
    "resolve_asset_path",
    "resolve_bundle",
    "set_asset_trace_enabled",
    "sha256_file",
    "summary_dict",
    "validate_published_bundle",
    "wipe_published_bundle",
    "write_manifest",
]
