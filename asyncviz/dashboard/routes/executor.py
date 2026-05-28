"""HTTP surface for executor-instrumentation diagnostics.

``GET /api/executor`` returns the live executor + work-item registry +
engine metrics + a trace tail. Backs the future executor-inspector UI
without scraping the bus.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from asyncviz.instrumentation.executor import build_executor_diagnostics

router = APIRouter(tags=["executor"])


class ExecutorDiagnosticsResponse(BaseModel):
    """Wire shape for ``GET /api/executor``."""

    model_config = ConfigDict(frozen=True)

    executor_registry_size: int
    executor_registry_finalized: int
    work_item_registry_size: int
    work_item_registry_finalized: int
    metrics: dict
    trace_enabled: bool = False
    trace_count: int = 0
    executors: list[dict] = Field(default_factory=list)
    work_items: list[dict] = Field(default_factory=list)


@router.get("/executor", response_model=ExecutorDiagnosticsResponse)
async def executor_diagnostics() -> ExecutorDiagnosticsResponse:
    snap = build_executor_diagnostics()
    payload = snap.to_dict()
    return ExecutorDiagnosticsResponse(
        executor_registry_size=snap.executor_registry_size,
        executor_registry_finalized=snap.executor_registry_finalized,
        work_item_registry_size=snap.work_item_registry_size,
        work_item_registry_finalized=snap.work_item_registry_finalized,
        metrics=payload["metrics"],
        trace_enabled=snap.trace_enabled,
        trace_count=snap.trace_count,
        executors=list(snap.executors),
        work_items=list(snap.work_items),
    )
