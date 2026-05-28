"""Backpressure helpers for the queue metrics engine.

Currently a thin marker module — the engine enforces the
``max_tracked_queues`` cap directly. Kept as a separate file so future
adaptive backpressure logic (priority-based eviction, sampling under
load, etc.) has a clean home that won't churn the engine module.
"""

from __future__ import annotations

from asyncviz.instrumentation.queue.metrics.queue_metrics_configuration import (
    QueueMetricsConfig,
)


def is_at_capacity(*, tracked_queues: int, config: QueueMetricsConfig) -> bool:
    return tracked_queues >= config.max_tracked_queues
