"""HTTP surface for gather-instrumentation diagnostics.

``GET /api/gather`` returns the live gather registry + engine metrics +
a trace tail. Backs the future await-dependency-graph UI without
scraping the bus.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from asyncviz.instrumentation.gather import build_gather_diagnostics

router = APIRouter(tags=["gather"])


class GatherDiagnosticsResponse(BaseModel):
    """Wire shape for ``GET /api/gather``."""

    model_config = ConfigDict(frozen=True)

    registry_size: int
    registry_finalized: int
    metrics: dict
    trace_enabled: bool = False
    trace_count: int = 0
    gathers: list[dict] = Field(default_factory=list)


@router.get("/gather", response_model=GatherDiagnosticsResponse)
async def gather_diagnostics() -> GatherDiagnosticsResponse:
    snap = build_gather_diagnostics()
    return GatherDiagnosticsResponse(
        registry_size=snap.registry_size,
        registry_finalized=snap.registry_finalized,
        metrics=snap.to_dict()["metrics"],
        trace_enabled=snap.trace_enabled,
        trace_count=snap.trace_count,
        gathers=list(snap.gathers),
    )
