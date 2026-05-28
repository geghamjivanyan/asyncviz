"""Runtime self-report for the packaging subsystem.

Consumed by the diagnostics endpoint + the CLI. The shape is
intentionally JSON-serializable so callers can plumb it through any
transport without an adapter layer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from asyncviz.packaging.assets import (
    AssetResolution,
    locate_frontend_bundle,
)
from asyncviz.packaging.build_metadata import BundleManifest
from asyncviz.packaging.versioning import (
    PackageMetadata,
    get_package_metadata,
)


@dataclass(frozen=True, slots=True)
class PackagingDiagnostics:
    """Operator-facing diagnostics for the packaging subsystem."""

    version: str
    channel: str
    is_editable: bool
    bundle_present: bool
    bundle_dir: str
    install_shape: str
    resolved_via: str
    bundle_file_count: int
    bundle_total_bytes: int
    manifest_source: str
    frontend_version: str | None
    frontend_build_id: str | None
    build_commit: str | None
    build_timestamp: str | None
    missing_files: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict view, safe for JSON serialization."""
        return asdict(self)


def build_packaging_diagnostics(
    metadata: PackageMetadata | None = None,
) -> PackagingDiagnostics:
    """Compose a :class:`PackagingDiagnostics` snapshot.

    Pass an existing :class:`PackageMetadata` to avoid re-walking the
    bundle directory; the diagnostics endpoint already has one in
    hand.
    """
    meta = metadata or get_package_metadata()
    resolution = meta.asset_resolution
    manifest = meta.bundle_manifest
    file_count, total_bytes = _bundle_size_summary(resolution, manifest)
    return PackagingDiagnostics(
        version=meta.version,
        channel=meta.build_identity.channel,
        is_editable=meta.is_editable,
        bundle_present=resolution.is_embedded,
        bundle_dir=str(resolution.bundle_dir),
        install_shape=resolution.install_shape.kind,
        resolved_via=resolution.resolved_via,
        bundle_file_count=file_count,
        bundle_total_bytes=total_bytes,
        manifest_source=manifest.source,
        frontend_version=manifest.frontend_version,
        frontend_build_id=manifest.build_id,
        build_commit=meta.build_identity.commit,
        build_timestamp=meta.build_identity.timestamp,
        missing_files=resolution.missing,
    )


# ── Internals ──────────────────────────────────────────────────────────


def _bundle_size_summary(
    resolution: AssetResolution,
    manifest: BundleManifest,
) -> tuple[int, int]:
    """Compute (file_count, total_bytes) from manifest + filesystem.

    Prefer the manifest when it carries entries — that's the cheapest
    source. Falls back to a directory walk when the manifest is empty
    or absent.
    """
    if manifest.entries:
        total = sum(entry.size_bytes for entry in manifest.entries)
        return (len(manifest.entries), total)
    bundle = resolution.bundle_dir
    if not bundle.is_dir():
        return (0, 0)
    count = 0
    total = 0
    for path in bundle.rglob("*"):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        count += 1
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return (count, total)


def locate_frontend_for_diagnostics() -> Path:
    """Convenience for CLI/diagnostics tools that just need the path."""
    return locate_frontend_bundle().bundle_dir
