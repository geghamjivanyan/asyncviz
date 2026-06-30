"""Static validator for a published frontend bundle.

Used by:

* :class:`FrontendAssetPublisher` as the post-publish smoke test.
* ``scripts/packaging/validate_frontend_assets.py`` for CI gates.
* Tests that want to assert "the bundle on disk is intact" without
  parsing chunks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from asyncviz.dashboard.assets.asset_integrity import sha256_file
from asyncviz.dashboard.assets.asset_layout import (
    ASSET_MANIFEST_VERSION,
    INDEX_HTML,
    REQUIRED_FILES,
)
from asyncviz.dashboard.assets.asset_manifest import load_manifest

Severity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class AssetValidationIssue:
    severity: Severity
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class AssetValidationReport:
    static_dir: Path
    file_count: int = 0
    total_bytes: int = 0
    issues: tuple[AssetValidationIssue, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def errors(self) -> tuple[AssetValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> tuple[AssetValidationIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")


def validate_published_bundle(static_dir: Path) -> AssetValidationReport:
    """Run every validation rule against the bundle at ``static_dir``."""
    if not static_dir.is_dir():
        return AssetValidationReport(
            static_dir=static_dir,
            issues=(AssetValidationIssue("error", "missing-dir", f"bundle missing: {static_dir}"),),
        )

    issues: list[AssetValidationIssue] = []
    for required in REQUIRED_FILES:
        if not (static_dir / required).is_file():
            issues.append(
                AssetValidationIssue("error", "missing-required", f"missing {required}"),
            )

    try:
        manifest = load_manifest(static_dir)
    except FileNotFoundError:
        issues.append(
            AssetValidationIssue(
                "warning",
                "missing-manifest",
                "no build.json — bundle was not produced by the canonical publisher",
            ),
        )
        manifest = None
    except Exception as exc:
        issues.append(
            AssetValidationIssue("error", "bad-manifest", f"failed to load build.json: {exc}"),
        )
        manifest = None

    file_count = 0
    total_bytes = 0
    if manifest is not None:
        if manifest.schema_version > ASSET_MANIFEST_VERSION:
            issues.append(
                AssetValidationIssue(
                    "error",
                    "schema-too-new",
                    (
                        f"manifest schema {manifest.schema_version} > "
                        f"supported {ASSET_MANIFEST_VERSION}"
                    ),
                ),
            )
        if not manifest.has_index:
            issues.append(
                AssetValidationIssue(
                    "error",
                    "missing-index-entry",
                    f"manifest does not include an {INDEX_HTML} entry",
                ),
            )
        for entry in manifest.entries:
            path = static_dir / entry.file
            if not path.is_file():
                issues.append(
                    AssetValidationIssue(
                        "error",
                        "missing-asset",
                        f"manifest references {entry.file} but the file is missing",
                    ),
                )
                continue
            actual_size = path.stat().st_size
            if actual_size != entry.size_bytes:
                issues.append(
                    AssetValidationIssue(
                        "error",
                        "size-mismatch",
                        (f"{entry.file}: manifest size {entry.size_bytes} != actual {actual_size}"),
                    ),
                )
            digest = sha256_file(path)
            if digest != entry.sha256:
                issues.append(
                    AssetValidationIssue(
                        "error",
                        "hash-mismatch",
                        f"{entry.file}: sha256 mismatch",
                    ),
                )
        file_count = manifest.total_files
        total_bytes = manifest.total_bytes
    else:
        # No manifest — walk the directory so the report still has counts.
        from asyncviz.dashboard.assets.asset_registry import collect_assets

        entries = collect_assets(static_dir)
        file_count = len(entries)
        total_bytes = sum(entry.size_bytes for entry in entries)

    return AssetValidationReport(
        static_dir=static_dir,
        file_count=file_count,
        total_bytes=total_bytes,
        issues=tuple(issues),
    )
