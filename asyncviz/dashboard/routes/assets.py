"""HTTP surface for the frontend-asset diagnostics.

Exposes ``GET /api/assets`` so the dashboard's diagnostics panel can
show the published-bundle state, manifest summary, validation
result, asset metrics + tracing — all without parsing the static
directory itself.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from asyncviz.dashboard.assets import build_asset_diagnostics

router = APIRouter(tags=["assets"])


class AssetDiagnosticsResponse(BaseModel):
    """Wire shape for ``GET /api/assets``."""

    model_config = ConfigDict(frozen=True)

    bundle: dict = Field(description="Resolved bundle directory + flags.")
    manifest: dict | None = Field(default=None, description="Manifest summary (build.json).")
    validation: dict = Field(description="Post-publish validation report.")
    metrics: dict = Field(default_factory=dict)
    cache_entries: int = 0
    trace_enabled: bool = False
    trace_count: int = 0


@router.get("/assets", response_model=AssetDiagnosticsResponse)
async def asset_diagnostics() -> AssetDiagnosticsResponse:
    snapshot = build_asset_diagnostics()
    return AssetDiagnosticsResponse(
        bundle=snapshot.bundle,
        manifest=snapshot.manifest,
        validation=snapshot.validation,
        metrics=snapshot.to_dict()["metrics"],
        cache_entries=snapshot.cache_entries,
        trace_enabled=snapshot.trace_enabled,
        trace_count=snapshot.trace_count,
    )
