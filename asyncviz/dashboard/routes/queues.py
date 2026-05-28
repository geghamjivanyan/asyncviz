"""HTTP surface for queue-instrumentation diagnostics.

``GET /api/queues`` returns the live queue registry + metrics + a
trace tail. Lets the dashboard's diagnostics panel + future
queue-inspector UI render queue topology without scraping the bus.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from asyncviz.instrumentation.queue import build_queue_diagnostics

router = APIRouter(tags=["queues"])


class QueueDiagnosticsResponse(BaseModel):
    """Wire shape for ``GET /api/queues``."""

    model_config = ConfigDict(frozen=True)

    registry_size: int
    registry_finalized: int
    metrics: dict
    trace_enabled: bool = False
    trace_count: int = 0
    queues: list[dict] = Field(default_factory=list)


@router.get("/queues", response_model=QueueDiagnosticsResponse)
async def queue_diagnostics() -> QueueDiagnosticsResponse:
    snap = build_queue_diagnostics()
    return QueueDiagnosticsResponse(
        registry_size=snap.registry_size,
        registry_finalized=snap.registry_finalized,
        metrics=snap.to_dict()["metrics"],
        trace_enabled=snap.trace_enabled,
        trace_count=snap.trace_count,
        queues=list(snap.queues),
    )
