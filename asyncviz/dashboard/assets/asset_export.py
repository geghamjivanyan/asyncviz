"""Export helpers for the published bundle.

Used by the future ``asyncviz config dump --assets`` flow + by the
CLI ``inspect-wheel-assets`` script to render the manifest to JSON
without hand-rolling the serialization.
"""

from __future__ import annotations

import json
from typing import Any

from asyncviz.dashboard.assets.asset_manifest import manifest_to_dict
from asyncviz.dashboard.assets.asset_metadata import AssetManifestModel


def manifest_to_json(manifest: AssetManifestModel, *, indent: int | None = None) -> str:
    """Render the manifest as canonical JSON (sorted keys)."""
    return json.dumps(
        manifest_to_dict(manifest),
        ensure_ascii=False,
        indent=indent,
        sort_keys=True,
    )


def summary_dict(manifest: AssetManifestModel) -> dict[str, Any]:
    """Compact view of the manifest — surfaced on diagnostics."""
    by_role: dict[str, int] = {}
    for entry in manifest.entries:
        by_role[entry.role] = by_role.get(entry.role, 0) + 1
    return {
        "schema_version": manifest.schema_version,
        "frontend_version": manifest.frontend_version,
        "built_at": manifest.built_at_iso,
        "commit": manifest.commit,
        "bundle_id": manifest.bundle_id,
        "total_files": manifest.total_files,
        "total_bytes": manifest.total_bytes,
        "by_role": by_role,
        "has_index": manifest.has_index,
    }
