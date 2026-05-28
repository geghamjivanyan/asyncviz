"""HTTP surface for the packaging diagnostics.

Exposes ``GET /api/packaging`` so operators (and the dashboard
diagnostics panel) can see how the deployed AsyncViz was packaged,
where it found its frontend, and which build identity it advertises.

The endpoint is intentionally cheap — it walks the embedded bundle
once per request to compute the file-count + total-bytes summary so
editable installs that rebuild the frontend immediately reflect new
counts without a restart.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from asyncviz.packaging import (
    PackagingDiagnostics,
    build_packaging_diagnostics,
)

router = APIRouter(tags=["packaging"])


class PackagingDiagnosticsResponse(BaseModel):
    """Wire shape for ``GET /api/packaging``.

    Mirrors :class:`asyncviz.packaging.PackagingDiagnostics`
    field-for-field; the Pydantic model exists so FastAPI emits a
    schema for the OpenAPI document.
    """

    model_config = ConfigDict(frozen=True)

    version: str = Field(description="Resolved package version.")
    channel: str = Field(description="Release channel (e.g. dev / nightly / stable).")
    is_editable: bool = Field(description="True when the package was installed in editable mode.")
    bundle_present: bool = Field(
        description="True when the embedded frontend bundle exists on disk.",
    )
    bundle_dir: str = Field(description="Absolute path of the bundle directory.")
    install_shape: str = Field(description="editable | packaged | unknown.")
    resolved_via: str = Field(description="importlib.resources | file-fallback.")
    bundle_file_count: int = Field(description="Number of files in the embedded bundle.")
    bundle_total_bytes: int = Field(description="Total bytes occupied by the embedded bundle.")
    manifest_source: str = Field(description="build.json | vite | scan | missing.")
    frontend_version: str | None = Field(default=None)
    frontend_build_id: str | None = Field(default=None)
    build_commit: str | None = Field(default=None)
    build_timestamp: str | None = Field(default=None)
    missing_files: list[str] = Field(default_factory=list)

    @classmethod
    def from_diagnostics(cls, d: PackagingDiagnostics) -> PackagingDiagnosticsResponse:
        return cls(
            version=d.version,
            channel=d.channel,
            is_editable=d.is_editable,
            bundle_present=d.bundle_present,
            bundle_dir=d.bundle_dir,
            install_shape=d.install_shape,
            resolved_via=d.resolved_via,
            bundle_file_count=d.bundle_file_count,
            bundle_total_bytes=d.bundle_total_bytes,
            manifest_source=d.manifest_source,
            frontend_version=d.frontend_version,
            frontend_build_id=d.frontend_build_id,
            build_commit=d.build_commit,
            build_timestamp=d.build_timestamp,
            missing_files=list(d.missing_files),
        )


@router.get("/packaging", response_model=PackagingDiagnosticsResponse)
async def packaging_diagnostics() -> PackagingDiagnosticsResponse:
    """Return packaging + bundle metadata for the installed runtime."""
    return PackagingDiagnosticsResponse.from_diagnostics(build_packaging_diagnostics())
