"""Replay helpers for the executor metrics engine."""

from __future__ import annotations

from collections.abc import Iterable

from asyncviz.instrumentation.executor.metrics.executor_metrics_engine import (
    ExecutorMetricsEngine,
)
from asyncviz.instrumentation.executor.metrics.executor_metrics_models import (
    ExecutorMetricsSnapshot,
)
from asyncviz.runtime.events.event import RuntimeEvent


def rebuild_executor_metrics_from_events(
    events: Iterable[RuntimeEvent],
    *,
    engine: ExecutorMetricsEngine | None = None,
) -> tuple[ExecutorMetricsEngine, ExecutorMetricsSnapshot, int]:
    """Reconstruct an executor metrics engine from a deterministic event
    stream.

    Returns ``(engine, snapshot, applied_count)``. When ``engine`` is
    omitted a fresh, *unbound* engine (no event bus) is built so the
    rebuild can't accidentally publish into a live runtime.
    """
    target = engine or ExecutorMetricsEngine(bus=None, emit_during_apply=False)
    applied = target.rebuild_from_events(events)
    return target, target.snapshot(), applied
