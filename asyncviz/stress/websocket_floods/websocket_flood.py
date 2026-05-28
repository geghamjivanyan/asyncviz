"""Websocket-subscriber flood.

The scenario simulates ``websocket_subscribers`` clients each
receiving ``websocket_events_per_subscriber`` events. A fraction
``slow_client_ratio`` is modeled as slow — events flow through a
small per-subscriber queue that the storm drains at a reduced rate.

The simulation never opens a real socket; the goal is to validate
the *backpressure + fanout* behavior, not the network stack.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from asyncviz.stress.failure_injection.failure_registry import (
    StressInjectedFailure,
)
from asyncviz.stress.harness.scenario_context import ScenarioContext


@dataclass(slots=True)
class _Subscriber:
    queue: deque[int]
    capacity: int
    slow: bool
    drained: int = 0
    dropped: int = 0
    disconnected: bool = False


async def run_websocket_flood(context: ScenarioContext) -> None:
    cfg = context.config
    subscribers: list[_Subscriber] = []
    slow_every = max(1, int(1.0 / max(cfg.slow_client_ratio, 1e-3)))
    capacity = max(4, cfg.websocket_events_per_subscriber // 8)
    for index in range(cfg.websocket_subscribers):
        subscribers.append(
            _Subscriber(
                queue=deque(maxlen=capacity),
                capacity=capacity,
                slow=(index % slow_every == 0),
            ),
        )
    backlog_peak = 0
    for event_index in range(cfg.websocket_events_per_subscriber):
        for sub in subscribers:
            if sub.disconnected:
                continue
            try:
                context.failure_injection.raise_if_triggered(
                    "websocket.disconnect",
                    detail=f"subscriber={id(sub)}",
                )
            except StressInjectedFailure:
                sub.disconnected = True
                context.record_signal("websocket-disconnect", "injected")
                continue
            if len(sub.queue) >= sub.capacity:
                sub.dropped += 1
                # Backpressure drops are expected behavior, not
                # failures — the scenario verifies the backlog stays
                # bounded.
                context.record_signal("custom", "websocket-drop")
                continue
            sub.queue.append(event_index)
        # Drain — slow clients drain at half rate, fast ones fully.
        for sub in subscribers:
            if sub.disconnected:
                continue
            drain_count = max(1, len(sub.queue) // (2 if sub.slow else 1))
            for _ in range(drain_count):
                if not sub.queue:
                    break
                sub.queue.popleft()
                sub.drained += 1
                context.record_signal("operation", "websocket-event")
        backlog = sum(len(s.queue) for s in subscribers)
        if backlog > backlog_peak:
            backlog_peak = backlog
    context.record_signal("custom", f"backlog_peak={backlog_peak}", float(backlog_peak))
