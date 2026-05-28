"""HTTP surface for queue-metrics diagnostics.

``GET /api/queues/metrics`` returns the live queue metrics engine
snapshot — per-queue occupancy / throughput / contention / pressure +
engine-level self-metrics + a tail of the trace ring. Backs the
queue-pressure overlays + future queue-inspector UI.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from asyncviz.instrumentation.queue.metrics import (
    QueueMetricsEngine,
    build_queue_metrics_diagnostics,
)

router = APIRouter(tags=["queues"])


class QueueMetricsResponse(BaseModel):
    """Wire shape for ``GET /api/queues/metrics``."""

    model_config = ConfigDict(frozen=True)

    queues: list[dict[str, Any]] = Field(default_factory=list)
    self_metrics: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    trace_enabled: bool = False
    trace_count: int = 0
    recent_trace: list[dict[str, Any]] = Field(default_factory=list)


def _resolve_engine(request: Request) -> QueueMetricsEngine | None:
    return getattr(request.app.state, "queue_metrics_engine", None)


@router.get("/queues/metrics", response_model=QueueMetricsResponse)
async def queue_metrics_diagnostics(request: Request) -> QueueMetricsResponse:
    engine = _resolve_engine(request)
    if engine is None:
        # Engine isn't wired (e.g. in a stripped-down test app). Return an
        # empty response rather than 500 — diagnostics endpoints should
        # gracefully degrade.
        return QueueMetricsResponse()
    snapshot = engine.snapshot()
    diagnostics = build_queue_metrics_diagnostics(snapshot)
    payload = diagnostics.to_dict()
    return QueueMetricsResponse(
        queues=payload["snapshot"]["queues"],
        self_metrics=payload["snapshot"]["self_metrics"],
        config=payload["snapshot"]["config"],
        trace_enabled=payload["trace_enabled"],
        trace_count=payload["trace_count"],
        recent_trace=payload["recent_trace"],
    )
