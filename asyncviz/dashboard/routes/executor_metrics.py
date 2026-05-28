"""HTTP surface for executor-metrics diagnostics.

``GET /api/executor/metrics`` returns the live executor metrics
engine snapshot — per-executor utilization / throughput / saturation
+ engine-level self-metrics + a tail of the trace ring.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from asyncviz.instrumentation.executor.metrics import (
    ExecutorMetricsEngine,
    build_executor_metrics_diagnostics,
)

router = APIRouter(tags=["executor"])


class ExecutorMetricsResponse(BaseModel):
    """Wire shape for ``GET /api/executor/metrics``."""

    model_config = ConfigDict(frozen=True)

    executors: list[dict[str, Any]] = Field(default_factory=list)
    self_metrics: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    trace_enabled: bool = False
    trace_count: int = 0
    recent_trace: list[dict[str, Any]] = Field(default_factory=list)


def _resolve_engine(request: Request) -> ExecutorMetricsEngine | None:
    return getattr(request.app.state, "executor_metrics_engine", None)


@router.get("/executor/metrics", response_model=ExecutorMetricsResponse)
async def executor_metrics_diagnostics(request: Request) -> ExecutorMetricsResponse:
    engine = _resolve_engine(request)
    if engine is None:
        return ExecutorMetricsResponse()
    snapshot = engine.snapshot()
    diagnostics = build_executor_metrics_diagnostics(snapshot)
    payload = diagnostics.to_dict()
    return ExecutorMetricsResponse(
        executors=payload["snapshot"]["executors"],
        self_metrics=payload["snapshot"]["self_metrics"],
        config=payload["snapshot"]["config"],
        trace_enabled=payload["trace_enabled"],
        trace_count=payload["trace_count"],
        recent_trace=payload["recent_trace"],
    )
