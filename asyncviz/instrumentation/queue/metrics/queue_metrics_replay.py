"""Replay helpers for the queue metrics engine.

The engine itself owns :meth:`rebuild_from_events`; this module exists
so external replay tooling has a stable, narrow surface to call
without poking at engine internals.
"""

from __future__ import annotations

from collections.abc import Iterable

from asyncviz.instrumentation.queue.metrics.queue_metrics_engine import (
    QueueMetricsEngine,
)
from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    QueueMetricsSnapshot,
)
from asyncviz.runtime.events.event import RuntimeEvent


def rebuild_metrics_from_events(
    events: Iterable[RuntimeEvent],
    *,
    engine: QueueMetricsEngine | None = None,
) -> tuple[QueueMetricsEngine, QueueMetricsSnapshot, int]:
    """Reconstruct a metrics engine from a deterministic event stream.

    If ``engine`` is omitted a fresh, *unbound* engine (no event bus) is
    built so the rebuild can't accidentally publish into a live runtime.
    Returns ``(engine, snapshot, applied_count)``.
    """
    target = engine or QueueMetricsEngine(bus=None, emit_during_apply=False)
    applied = target.rebuild_from_events(events)
    return target, target.snapshot(), applied
