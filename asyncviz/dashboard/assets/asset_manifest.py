"""Read / write the AsyncViz frontend publish manifest (``build.json``).

The manifest is the canonical "what's inside this published bundle"
record. It carries:

* schema version,
* frontend version + build identity (commit, timestamp),
* per-file entries with size + sha256 + role + content-type,
* a bundle id (uuid) the diagnostics endpoint surfaces.

Both the publisher and the validator round-trip through this file —
no parallel data structures.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from asyncviz.dashboard.assets.asset_integrity import atomic_write_text
from asyncviz.dashboard.assets.asset_layout import (
    ASSET_MANIFEST_FILENAME,
    ASSET_MANIFEST_VERSION,
)
from asyncviz.dashboard.assets.asset_metadata import (
    AssetManifestModel,
    AssetMetadata,
    AssetRole,
)


def build_manifest_model(
    *,
    entries: tuple[AssetMetadata, ...],
    frontend_version: str | None,
    built_at_iso: str,
    commit: str | None,
    bundle_id: str | None = None,
    extras: dict[str, Any] | None = None,
) -> AssetManifestModel:
    total_bytes = sum(entry.size_bytes for entry in entries)
    return AssetManifestModel(
        schema_version=ASSET_MANIFEST_VERSION,
        frontend_version=frontend_version,
        built_at_iso=built_at_iso,
        commit=commit,
        bundle_id=bundle_id or str(uuid.uuid4()),
        entries=entries,
        total_files=len(entries),
        total_bytes=total_bytes,
        extras=dict(extras or {}),
    )


def write_manifest(static_dir: Path, manifest: AssetManifestModel) -> Path:
    """Persist ``manifest`` to ``static_dir/build.json`` atomically."""
    path = static_dir / ASSET_MANIFEST_FILENAME
    payload = manifest_to_dict(manifest)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return path


def load_manifest(static_dir: Path) -> AssetManifestModel:
    """Read + parse ``static_dir/build.json``.

    Raises ``FileNotFoundError`` when the manifest is missing.
    """
    path = static_dir / ASSET_MANIFEST_FILENAME
    if not path.is_file():
        raise FileNotFoundError(f"asset manifest missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return manifest_from_dict(payload)


def manifest_to_dict(manifest: AssetManifestModel) -> dict[str, Any]:
    return {
        "schema_version": manifest.schema_version,
        "frontend_version": manifest.frontend_version,
        "built_at_iso": manifest.built_at_iso,
        "commit": manifest.commit,
        "bundle_id": manifest.bundle_id,
        "total_files": manifest.total_files,
        "total_bytes": manifest.total_bytes,
        "entries": [asdict(entry) for entry in manifest.entries],
        "extras": dict(manifest.extras),
    }


def manifest_from_dict(payload: dict[str, Any]) -> AssetManifestModel:
    raw_entries = payload.get("entries") or []
    entries: list[AssetMetadata] = []
    for raw in raw_entries:
        role: AssetRole = raw.get("role", "other")
        if role not in ("entry", "asset", "index", "manifest", "other"):
            role = "other"
        entries.append(
            AssetMetadata(
                file=str(raw["file"]),
                role=role,
                size_bytes=int(raw.get("size_bytes", 0)),
                sha256=str(raw.get("sha256", "")),
                content_type=str(raw.get("content_type", "application/octet-stream")),
            ),
        )
    return AssetManifestModel(
        schema_version=int(payload.get("schema_version", ASSET_MANIFEST_VERSION)),
        frontend_version=payload.get("frontend_version"),
        built_at_iso=str(payload.get("built_at_iso", "")),
        commit=payload.get("commit"),
        bundle_id=str(payload.get("bundle_id", "")),
        entries=tuple(entries),
        total_files=int(payload.get("total_files", len(entries))),
        total_bytes=int(payload.get("total_bytes", sum(e.size_bytes for e in entries))),
        extras=dict(payload.get("extras", {})),
    )
