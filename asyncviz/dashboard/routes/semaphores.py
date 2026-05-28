"""HTTP surface for semaphore-instrumentation diagnostics.

``GET /api/semaphores`` returns the live semaphore registry +
engine metrics + a trace tail. Backs the future contention overlay
+ semaphore inspector UI without scraping the bus.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from asyncviz.instrumentation.semaphore import build_semaphore_diagnostics

router = APIRouter(tags=["semaphores"])


class SemaphoreDiagnosticsResponse(BaseModel):
    """Wire shape for ``GET /api/semaphores``."""

    model_config = ConfigDict(frozen=True)

    registry_size: int
    registry_finalized: int
    metrics: dict
    trace_enabled: bool = False
    trace_count: int = 0
    semaphores: list[dict] = Field(default_factory=list)


@router.get("/semaphores", response_model=SemaphoreDiagnosticsResponse)
async def semaphore_diagnostics() -> SemaphoreDiagnosticsResponse:
    snap = build_semaphore_diagnostics()
    return SemaphoreDiagnosticsResponse(
        registry_size=snap.registry_size,
        registry_finalized=snap.registry_finalized,
        metrics=snap.to_dict()["metrics"],
        trace_enabled=snap.trace_enabled,
        trace_count=snap.trace_count,
        semaphores=list(snap.semaphores),
    )
