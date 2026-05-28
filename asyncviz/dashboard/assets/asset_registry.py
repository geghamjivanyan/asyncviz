"""Walk a directory tree and build the canonical asset list.

Pure file-system → typed-records mapping. Splits the "discover" step
from the "publish" step so tests can inspect what the registry sees
without writing anything to disk.
"""

from __future__ import annotations

from pathlib import Path

from asyncviz.dashboard.assets.asset_integrity import (
    content_type_for,
    sha256_file,
)
from asyncviz.dashboard.assets.asset_layout import (
    ASSETS_DIRECTORY,
    IGNORED_FILES,
    INDEX_HTML,
    VITE_MANIFEST_FILENAME,
)
from asyncviz.dashboard.assets.asset_metadata import (
    AssetMetadata,
    AssetRole,
)


def _classify(relative: str) -> AssetRole:
    if relative == INDEX_HTML:
        return "index"
    if relative == VITE_MANIFEST_FILENAME:
        return "manifest"
    if relative.startswith(f"{ASSETS_DIRECTORY}/"):
        # ``index-*.js`` is the bootstrap entry chunk; everything else
        # under assets/ is a hashed dependency.
        leaf = relative.rsplit("/", 1)[-1]
        if leaf.startswith("index-") and (leaf.endswith(".js") or leaf.endswith(".mjs")):
            return "entry"
        return "asset"
    return "other"


def collect_assets(static_dir: Path) -> tuple[AssetMetadata, ...]:
    """Enumerate every file under ``static_dir`` as an :class:`AssetMetadata`.

    Returns an empty tuple when the directory is missing. Sorted by
    POSIX-relative path so the result is deterministic across
    platforms with arbitrary directory-iteration order.
    """
    if not static_dir.is_dir():
        return ()
    entries: list[AssetMetadata] = []
    root_resolved = static_dir.resolve()
    for path in static_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.name in IGNORED_FILES:
            continue
        relative = path.resolve().relative_to(root_resolved).as_posix()
        entries.append(
            AssetMetadata(
                file=relative,
                role=_classify(relative),
                size_bytes=path.stat().st_size,
                sha256=sha256_file(path),
                content_type=content_type_for(path),
            ),
        )
    entries.sort(key=lambda e: e.file)
    return tuple(entries)
