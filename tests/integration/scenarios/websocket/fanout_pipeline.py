"""Websocket fanout integration scenario.

Each subscriber gets one ``operation`` signal per delivered event;
overflow (when a subscriber's queue is full) is recorded as a
``custom`` signal so it doesn't poison the failure budget. A peak-
backlog ``custom`` signal lets the runner check the
``max_websocket_backlog`` threshold.
"""

from __future__ import annotations

from collections import deque

from tests.integration.harness.scenario_context import IntegrationContext


async def run_websocket_fanout_pipeline(context: IntegrationContext) -> None:
    cfg = context.config
    capacity = max(4, cfg.websocket_events // 8)
    subscribers = [
        deque(maxlen=capacity) for _ in range(cfg.websocket_subscribers)
    ]
    backlog_peak = 0
    for event_index in range(cfg.websocket_events):
        for queue in subscribers:
            if len(queue) >= capacity:
                context.record("custom", "ws-overflow")
                continue
            queue.append(event_index)
        # Drain — every other tick.
        if event_index % 2 == 0:
            for queue in subscribers:
                if queue:
                    queue.popleft()
                    context.record("operation", "ws-deliver")
        backlog = sum(len(q) for q in subscribers)
        if backlog > backlog_peak:
            backlog_peak = backlog
    context.record(
        "custom", f"backlog_peak={backlog_peak}", value=float(backlog_peak),
    )
