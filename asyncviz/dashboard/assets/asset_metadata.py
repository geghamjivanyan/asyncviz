"""Typed metadata records for the published frontend bundle.

Split from the publisher so the schema is reusable from the
validator + runtime resolver + diagnostics endpoint without
dragging the build pipeline into their import graphs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AssetRole = Literal["entry", "asset", "index", "manifest", "other"]


@dataclass(frozen=True, slots=True)
class AssetMetadata:
    """One file inside the published bundle."""

    file: str
    """POSIX-relative path under the static root (e.g.
    ``assets/index-AbC123.js``)."""

    role: AssetRole
    """Coarse classification consumed by the diagnostics renderer."""

    size_bytes: int
    sha256: str
    content_type: str


@dataclass(frozen=True, slots=True)
class AssetManifestModel:
    """Schema of the published-bundle manifest (``build.json``)."""

    schema_version: int
    frontend_version: str | None
    built_at_iso: str
    commit: str | None
    bundle_id: str
    entries: tuple[AssetMetadata, ...] = field(default_factory=tuple)
    total_files: int = 0
    total_bytes: int = 0
    extras: dict[str, Any] = field(default_factory=dict)

    def find(self, file: str) -> AssetMetadata | None:
        for entry in self.entries:
            if entry.file == file:
                return entry
        return None

    @property
    def has_index(self) -> bool:
        return any(entry.role == "index" for entry in self.entries)
