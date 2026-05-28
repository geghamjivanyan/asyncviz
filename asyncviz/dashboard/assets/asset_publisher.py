"""Canonical orchestrator for publishing the embedded frontend.

The publisher composes the smaller modules:

  1. (optional) :class:`FrontendBuilder` runs ``npm run build``.
  2. :func:`wipe_published_bundle` clears the previous embed.
  3. :func:`copy_bundle` mirrors ``frontend/dist`` into
     ``asyncviz/dashboard/static``.
  4. :func:`collect_assets` walks the published tree.
  5. :func:`build_manifest_model` + :func:`write_manifest` emit
     ``build.json``.
  6. :func:`validate_published_bundle` confirms the bundle is well-
     formed before returning.

Returns a :class:`PublishResult` consumed by the CLI scripts +
package tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from asyncviz.dashboard.assets.asset_build import (
    FrontendBuilder,
    FrontendBuildOutcome,
    NpmFrontendBuilder,
)
from asyncviz.dashboard.assets.asset_manifest import (
    build_manifest_model,
    write_manifest,
)
from asyncviz.dashboard.assets.asset_metadata import AssetManifestModel
from asyncviz.dashboard.assets.asset_observability import get_asset_metrics
from asyncviz.dashboard.assets.asset_packaging import (
    copy_bundle,
    wipe_published_bundle,
)
from asyncviz.dashboard.assets.asset_registry import collect_assets
from asyncviz.dashboard.assets.asset_tracing import record_asset_trace
from asyncviz.dashboard.assets.asset_validation import (
    AssetValidationReport,
    validate_published_bundle,
)
from asyncviz.dashboard.assets.asset_versioning import (
    current_build_timestamp,
    read_frontend_version,
    read_git_commit,
)


@dataclass(frozen=True, slots=True)
class PublishResult:
    """End-state surfaced to the calling script."""

    success: bool
    manifest: AssetManifestModel | None
    static_dir: Path
    files_copied: int
    files_removed: int
    build_outcome: FrontendBuildOutcome | None
    validation: AssetValidationReport
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class FrontendAssetPublisher:
    """Composed asset publisher.

    Dependencies are injectable so tests + the CLI's
    ``--skip-build`` flag can drive a noop builder without going
    through ``npm``.
    """

    repo_root: Path
    static_dir: Path
    frontend_dir: Path
    builder: FrontendBuilder = field(default_factory=NpmFrontendBuilder)

    def publish(
        self,
        *,
        skip_build: bool = False,
        skip_clean: bool = False,
        dry_run: bool = False,
    ) -> PublishResult:
        notes: list[str] = []
        build_outcome: FrontendBuildOutcome | None = None

        if not skip_build:
            build_outcome = self.builder.build(frontend_dir=self.frontend_dir)
            if not build_outcome.success:
                return PublishResult(
                    success=False,
                    manifest=None,
                    static_dir=self.static_dir,
                    files_copied=0,
                    files_removed=0,
                    build_outcome=build_outcome,
                    validation=AssetValidationReport(static_dir=self.static_dir),
                    notes=("frontend build failed; see build_outcome.detail",),
                )
            notes.append("frontend build succeeded")
        else:
            notes.append("skipped frontend build (--skip-build)")

        dist_dir = self.frontend_dir / "dist"
        if not (dist_dir / "index.html").is_file():
            return PublishResult(
                success=False,
                manifest=None,
                static_dir=self.static_dir,
                files_copied=0,
                files_removed=0,
                build_outcome=build_outcome,
                validation=AssetValidationReport(static_dir=self.static_dir),
                notes=(*notes, f"no dist/index.html at {dist_dir}"),
            )

        if dry_run:
            entries = collect_assets(dist_dir)
            manifest = build_manifest_model(
                entries=entries,
                frontend_version=read_frontend_version(self.frontend_dir / "package.json"),
                built_at_iso=current_build_timestamp(),
                commit=read_git_commit(self.repo_root),
            )
            return PublishResult(
                success=True,
                manifest=manifest,
                static_dir=self.static_dir,
                files_copied=0,
                files_removed=0,
                build_outcome=build_outcome,
                validation=AssetValidationReport(static_dir=self.static_dir),
                notes=(*notes, "dry-run; nothing written"),
            )

        record_asset_trace("publish-start", str(self.static_dir))

        files_removed = 0 if skip_clean else wipe_published_bundle(self.static_dir)
        if skip_clean:
            notes.append("skipped clean (--skip-clean)")
        else:
            record_asset_trace("publish-clean", f"removed={files_removed}")
        files_copied = copy_bundle(dist_dir, self.static_dir)
        record_asset_trace("publish-copy", f"copied={files_copied}")
        notes.append(f"copied {files_copied} files into {self.static_dir}")

        entries = collect_assets(self.static_dir)
        manifest = build_manifest_model(
            entries=entries,
            frontend_version=read_frontend_version(self.frontend_dir / "package.json"),
            built_at_iso=current_build_timestamp(),
            commit=read_git_commit(self.repo_root),
        )
        write_manifest(self.static_dir, manifest)
        record_asset_trace(
            "publish-manifest",
            f"entries={manifest.total_files} bytes={manifest.total_bytes}",
        )

        validation = validate_published_bundle(self.static_dir)
        record_asset_trace(
            "publish-validate",
            f"ok={validation.ok} issues={len(validation.issues)}",
        )
        success = validation.ok
        get_asset_metrics().record_publish(
            ok=success,
            files_copied=files_copied,
            files_removed=files_removed,
        )
        get_asset_metrics().record_validation(ok=validation.ok)
        record_asset_trace(
            "publish-finished" if success else "publish-failed",
            f"copied={files_copied} removed={files_removed}",
        )
        return PublishResult(
            success=success,
            manifest=manifest,
            static_dir=self.static_dir,
            files_copied=files_copied,
            files_removed=files_removed,
            build_outcome=build_outcome,
            validation=validation,
            notes=tuple(notes),
        )
