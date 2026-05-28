"""Runtime asset-path resolution.

Wraps the canonical
:func:`asyncviz.packaging.assets.locate_frontend_bundle` so callers
that already think in terms of the new dashboard-assets module don't
have to know the packaging layer exists. Adds an in-process cache
so repeated lookups are O(1) — the bundle directory doesn't move
during a process lifetime.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from asyncviz.dashboard.assets.asset_layout import (
    ASSET_MANIFEST_FILENAME,
    INDEX_HTML,
)
from asyncviz.dashboard.assets.asset_manifest import load_manifest
from asyncviz.dashboard.assets.asset_metadata import AssetManifestModel
from asyncviz.packaging import locate_frontend_bundle


@dataclass(frozen=True, slots=True)
class ResolvedBundle:
    """Aggregate view of one resolved on-disk bundle."""

    bundle_dir: Path
    index_path: Path
    is_published: bool
    manifest: AssetManifestModel | None


_lock = threading.Lock()
_cache: ResolvedBundle | None = None


def resolve_bundle(*, refresh: bool = False) -> ResolvedBundle:
    """Return the resolved bundle. Cached in-process; pass
    ``refresh=True`` to invalidate."""
    global _cache
    with _lock:
        if _cache is not None and not refresh:
            return _cache
        resolution = locate_frontend_bundle()
        index = resolution.bundle_dir / INDEX_HTML
        manifest: AssetManifestModel | None = None
        try:
            if (resolution.bundle_dir / ASSET_MANIFEST_FILENAME).is_file():
                manifest = load_manifest(resolution.bundle_dir)
        except Exception:  # pragma: no cover — defensive
            manifest = None
        bundle = ResolvedBundle(
            bundle_dir=resolution.bundle_dir,
            index_path=index,
            is_published=index.is_file(),
            manifest=manifest,
        )
        _cache = bundle
        return bundle


def resolve_asset_path(relative: str) -> Path | None:
    """Resolve one asset under the bundle. Returns ``None`` when
    outside the bundle or missing."""
    bundle = resolve_bundle()
    root = bundle.bundle_dir.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def reset_resolution_cache() -> None:
    """Clear the cached resolution — used by tests + the
    ``--refresh`` flag of validation scripts."""
    global _cache
    with _lock:
        _cache = None
