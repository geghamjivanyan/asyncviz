"""Embedded-bundle build manifest reader.

The frontend build is allowed to drop a small ``build.json`` next to
its assets so the backend can surface:

* the frontend version (independent from the package version),
* a build id (commit short hash or CI run id),
* a build timestamp (ISO-8601 UTC),
* the names of the entry chunks (used to verify the bundle is intact),
* the Vite manifest entries (for the diagnostics endpoint).

The file is *optional*. When it's missing we fall back to a
synthetic manifest that scans the static directory + reads the Vite
``manifest.json`` if available. Either way the consumer sees the same
:class:`BundleManifest` shape so call sites stay simple.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from asyncviz.utils.logging import get_logger

logger = get_logger("packaging.build_metadata")

_BUILD_JSON = "build.json"
_VITE_MANIFEST = ".vite/manifest.json"
_INDEX_HTML = "index.html"
_ASSETS_DIR = "assets"

ManifestSource = Literal["build.json", "vite", "scan", "missing"]


@dataclass(frozen=True, slots=True)
class BundleManifestEntry:
    """One file in the build manifest.

    ``role`` summarizes what the file is for: ``"entry"`` for the
    top-level bootstrap chunk, ``"asset"`` for hashed assets,
    ``"index"`` for ``index.html`` itself.
    """

    file: str
    role: Literal["entry", "asset", "index", "other"]
    size_bytes: int


@dataclass(frozen=True, slots=True)
class BundleManifest:
    """Parsed view of the embedded-frontend build manifest."""

    source: ManifestSource
    frontend_version: str | None
    build_id: str | None
    built_at: str | None
    commit: str | None
    entries: tuple[BundleManifestEntry, ...] = field(default_factory=tuple)

    @property
    def is_present(self) -> bool:
        return self.source != "missing"

    def find(self, file: str) -> BundleManifestEntry | None:
        for entry in self.entries:
            if entry.file == file:
                return entry
        return None


# ── Public loader ───────────────────────────────────────────────────────


def load_bundle_manifest(bundle_dir: Path) -> BundleManifest:
    """Load the manifest from ``bundle_dir``.

    Resolution order:

    1. ``bundle_dir/build.json`` — the AsyncViz-specific schema we
       control. Highest fidelity (carries versions + commit +
       timestamp).
    2. ``bundle_dir/.vite/manifest.json`` — the Vite-emitted manifest.
       Carries the entry chunks but not version metadata.
    3. Filesystem scan — best-effort enumeration of files inside the
       bundle dir.
    4. ``BundleManifest(source="missing", …)`` when the directory
       itself is absent.
    """
    if not bundle_dir.is_dir():
        return BundleManifest(
            source="missing",
            frontend_version=None,
            build_id=None,
            built_at=None,
            commit=None,
        )

    build_json = bundle_dir / _BUILD_JSON
    if build_json.is_file():
        manifest = _load_build_json(bundle_dir, build_json)
        if manifest is not None:
            return manifest

    vite_manifest = bundle_dir / _VITE_MANIFEST
    if vite_manifest.is_file():
        manifest = _load_vite_manifest(bundle_dir, vite_manifest)
        if manifest is not None:
            return manifest

    return _scan_bundle(bundle_dir)


# ── Internals ──────────────────────────────────────────────────────────


def _load_build_json(bundle_dir: Path, path: Path) -> BundleManifest | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None
    entries_raw = payload.get("entries") or []
    entries: list[BundleManifestEntry] = []
    for entry in entries_raw:
        file = entry.get("file")
        if not file:
            continue
        role = entry.get("role", "other")
        if role not in ("entry", "asset", "index", "other"):
            role = "other"
        size_bytes = _safe_size(bundle_dir / file)
        entries.append(BundleManifestEntry(file=file, role=role, size_bytes=size_bytes))
    if not entries:
        # build.json is empty — fall back to a scan so callers still
        # see file-level entries.
        scan = _scan_bundle(bundle_dir)
        entries = list(scan.entries)
    return BundleManifest(
        source="build.json",
        frontend_version=payload.get("frontend_version"),
        build_id=payload.get("build_id"),
        built_at=payload.get("built_at"),
        commit=payload.get("commit"),
        entries=tuple(entries),
    )


def _load_vite_manifest(bundle_dir: Path, path: Path) -> BundleManifest | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None
    entries: list[BundleManifestEntry] = []
    for key, info in payload.items():
        file = info.get("file")
        if not file:
            continue
        role: Literal["entry", "asset", "index", "other"]
        role = "entry" if info.get("isEntry") else "asset"
        if key == _INDEX_HTML:
            role = "index"
        entries.append(
            BundleManifestEntry(
                file=file,
                role=role,
                size_bytes=_safe_size(bundle_dir / file),
            ),
        )
    if not entries:
        return None
    entries.sort(key=lambda e: e.file)
    return BundleManifest(
        source="vite",
        frontend_version=None,
        build_id=None,
        built_at=None,
        commit=None,
        entries=tuple(entries),
    )


def _scan_bundle(bundle_dir: Path) -> BundleManifest:
    entries: list[BundleManifestEntry] = []
    index = bundle_dir / _INDEX_HTML
    if index.is_file():
        entries.append(
            BundleManifestEntry(file=_INDEX_HTML, role="index", size_bytes=_safe_size(index)),
        )
    assets_dir = bundle_dir / _ASSETS_DIR
    if assets_dir.is_dir():
        for asset in sorted(assets_dir.rglob("*"), key=lambda p: p.as_posix()):
            if not asset.is_file():
                continue
            relative = asset.relative_to(bundle_dir).as_posix()
            entries.append(
                BundleManifestEntry(file=relative, role="asset", size_bytes=_safe_size(asset)),
            )
    return BundleManifest(
        source="scan",
        frontend_version=None,
        build_id=None,
        built_at=None,
        commit=None,
        entries=tuple(entries),
    )


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0
