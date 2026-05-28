"""Wire models for the frontend-serving diagnostics endpoint.

``GET /api/runtime/frontend`` returns :class:`FrontendInfoResponse` —
a small inventory of what the service is actually serving. Frontend
bootstrap code reads this to display the active build version /
manifest source; operators read it to confirm a deployment landed
correctly.

Pydantic models live here so the route module stays a thin
translation layer.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

#: Bumped on incompatible shape changes to :class:`FrontendInfoResponse`.
FRONTEND_PROTOCOL_VERSION = 1


class FrontendManifestEntry(BaseModel):
    """Wire shape of one :class:`ManifestEntry`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: str
    name: str
    is_entry: bool = False
    css: list[str] = Field(default_factory=list)


class FrontendInfoResponse(BaseModel):
    """Operational view of the static frontend serving layer.

    Returned by ``GET /api/runtime/frontend``. Frontend bootstrap code
    can use ``entry_module`` / ``entry_css`` to inject hydration data
    matched to the current build; operators read ``source`` to confirm
    the manifest is real vs. synthetic; ``asset_size_bytes`` flags
    bundle bloat regressions across deployments.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol_version: int = FRONTEND_PROTOCOL_VERSION
    mode: str
    static_dir: str
    bundle_present: bool
    assets_dir_present: bool
    asset_count: int
    asset_size_bytes: int
    entry_module: str | None = None
    entry_css: list[str] = Field(default_factory=list)
    manifest_source: str
    manifest_entries: list[FrontendManifestEntry] = Field(default_factory=list)


class FrontendServingMetricsResponse(BaseModel):
    """Wire shape of :class:`FrontendServingMetricsSnapshot`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_requests: int
    asset_hits: int
    asset_misses: int
    immutable_hits: int
    loose_hits: int
    index_served: int
    spa_fallbacks: int
    reserved_blocked: int
    path_traversal_blocked: int
    manifest_loads: int
    manifest_load_failures: int
