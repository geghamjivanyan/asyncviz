"""Canonical internal event queue + dispatcher.

Public surface:

* :class:`InternalEventQueue` — the runtime's authoritative event transport.
  Owned by the dashboard lifespan; sits between instrumentation and the
  :class:`asyncviz.runtime.events.EventBus` subscriber registry.
* :class:`QueuedEvent` — an event plus its allocated sequence.
* :class:`OverflowStrategy` — how the queue behaves when full.
* :class:`RetentionBuffer` — replay-oriented ring buffer.
* :class:`QueueMetrics` / :class:`QueueMetricsSnapshot` — observability.
* :class:`QueueSnapshotResponse` / :class:`ReplayResult` — JSON-safe outputs.
* exceptions — :class:`EventQueueError`, :class:`EventQueueNotRunningError`,
  :class:`EventQueueOverflowError`, :class:`RetentionConfigError`.

Design rule: a runtime has exactly **one** :class:`InternalEventQueue`. It
is created by the dashboard lifespan and shared by every producer (the
patcher, the bridge, future replay recorders). Sequence numbers are
allocated by the queue from the runtime's :class:`RuntimeClock`, so they
form a single ordering domain.
"""

from asyncviz.runtime.queue.backpressure import (
    DEFAULT_OVERFLOW_STRATEGY,
    OverflowStrategy,
)
from asyncviz.runtime.queue.buffering import QueuedEvent
from asyncviz.runtime.queue.channels import EventChannel
from asyncviz.runtime.queue.dispatcher import PostDispatchHook, QueueDispatcher
from asyncviz.runtime.queue.event_queue import (
    DEFAULT_CAPACITY,
    DEFAULT_RETENTION,
    InternalEventQueue,
)
from asyncviz.runtime.queue.exceptions import (
    EventQueueError,
    EventQueueNotRunningError,
    EventQueueOverflowError,
    RetentionConfigError,
)
from asyncviz.runtime.queue.metrics import QueueMetrics, QueueMetricsSnapshot
from asyncviz.runtime.queue.retention import RetentionBuffer
from asyncviz.runtime.queue.snapshots import QueueSnapshotResponse, ReplayResult

__all__ = [
    "DEFAULT_CAPACITY",
    "DEFAULT_OVERFLOW_STRATEGY",
    "DEFAULT_RETENTION",
    "EventChannel",
    "EventQueueError",
    "EventQueueNotRunningError",
    "EventQueueOverflowError",
    "InternalEventQueue",
    "OverflowStrategy",
    "PostDispatchHook",
    "QueueDispatcher",
    "QueueMetrics",
    "QueueMetricsSnapshot",
    "QueueSnapshotResponse",
    "QueuedEvent",
    "ReplayResult",
    "RetentionBuffer",
    "RetentionConfigError",
]
