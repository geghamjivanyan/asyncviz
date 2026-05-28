"""Runtime event models for the queue metrics engine.

These events are the *output* of :class:`QueueMetricsEngine`; raw queue
events (``asyncio.queue.put`` etc. — see :mod:`.queue`) are the input.
The engine emits one of these whenever a per-queue aggregate transitions
in a way the dashboard cares about:

* :class:`QueueMetricsUpdatedEvent` — periodic / debounced snapshot of a
  queue's aggregated state. Carries occupancy, throughput, contention,
  and pressure. Pull this for dashboard tiles + charts.
* :class:`QueuePressureChangedEvent` — pressure level crossed a band
  (calm → warning → critical or vice versa). Hysteresis-gated so it
  doesn't flicker.
* :class:`QueueContentionDetectedEvent` — blocked producers / consumers
  appeared on a previously-quiet queue, or jumped over a configured
  threshold.
* :class:`QueueSaturationDetectedEvent` — occupancy crossed the
  saturation ratio (default 0.9). Reverse-fires when it drops back
  below the recovery threshold.

Payload semantics:

* Every event carries the queue's identity (``queue_id``, ``queue_kind``,
  ``maxsize``) so a consumer can resolve the queue without keeping the
  metrics engine in scope.
* Numeric fields are intentionally compact + flat so the wire shape stays
  small under high churn.
* ``snapshot`` carries a frozen, JSON-safe dict view of every per-queue
  sub-snapshot at the moment the event fired. Renderers can either chart
  the flat fields directly or descend into ``snapshot`` for the full view.
* No user payloads or queue items are ever captured — same redaction
  policy as the underlying queue events.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from asyncviz.runtime.events.models.base import RuntimeEvent


class _QueueMetricsEventBase(RuntimeEvent):
    """Shared envelope for every queue-metrics event."""

    queue_id: str
    queue_kind: str
    """``Queue`` / ``PriorityQueue`` / ``LifoQueue`` / ``subclass`` / ``unknown``."""
    maxsize: int = 0
    sequence: int = 0
    """Monotonic per-queue revision counter — every per-queue emission
    bumps it. Lets clients ignore stale events after a reconnect."""
    snapshot: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueueMetricsUpdatedEvent(_QueueMetricsEventBase):
    """Debounced snapshot of a queue's aggregated metrics."""

    event_type: Literal["asyncio.queue.metrics.updated"] = "asyncio.queue.metrics.updated"

    current_size: int = 0
    peak_size: int = 0
    occupancy_ratio: float = 0.0
    """``current_size / maxsize`` (0.0 when unbounded)."""
    mean_occupancy: float = 0.0

    put_rate: float = 0.0
    get_rate: float = 0.0
    put_count: int = 0
    get_count: int = 0
    producer_consumer_delta: int = 0
    """``put_count - get_count``; positive means producers outrunning consumers."""

    blocked_producers: int = 0
    blocked_consumers: int = 0
    blocked_put_count: int = 0
    blocked_get_count: int = 0
    cancelled_count: int = 0

    pressure_score: float = 0.0
    pressure_level: str = "calm"
    """``calm`` / ``warning`` / ``critical``."""


class QueuePressureChangedEvent(_QueueMetricsEventBase):
    """Emitted when a queue's pressure band transitions.

    Hysteresis-gated: a queue must cross the upper band threshold to escalate
    and fall below the lower band threshold (``threshold - hysteresis``) to
    de-escalate. Prevents flicker on noisy queues.
    """

    event_type: Literal["asyncio.queue.pressure.changed"] = "asyncio.queue.pressure.changed"

    previous_level: str = "calm"
    new_level: str = "calm"
    pressure_score: float = 0.0
    occupancy_ratio: float = 0.0
    blocked_producers: int = 0
    blocked_consumers: int = 0


class QueueContentionDetectedEvent(_QueueMetricsEventBase):
    """Emitted when blocked producers / consumers appear on a queue.

    Fires on the leading edge — when the count rises from 0 to ≥1, or
    crosses a configured threshold. Pairs with a future ``contention.cleared``
    when the count drops back to 0 (not yet wired — kept open by design so
    new event types can land without bumping the protocol).
    """

    event_type: Literal["asyncio.queue.contention.detected"] = (
        "asyncio.queue.contention.detected"
    )

    blocked_producers: int = 0
    blocked_consumers: int = 0
    blocked_put_total: int = 0
    blocked_get_total: int = 0
    contention_kind: Literal["producers", "consumers", "both"] = "producers"


class QueueSaturationDetectedEvent(_QueueMetricsEventBase):
    """Emitted when ``occupancy_ratio`` first crosses the saturation threshold."""

    event_type: Literal["asyncio.queue.saturation.detected"] = (
        "asyncio.queue.saturation.detected"
    )

    occupancy_ratio: float = 0.0
    current_size: int = 0
    threshold: float = 0.9


#: Canonical ordered list of every queue-metrics event type. Mirrored in
#: :data:`asyncviz.runtime.events.models.enums.EventType`.
QUEUE_METRICS_EVENT_TYPES: tuple[str, ...] = (
    "asyncio.queue.metrics.updated",
    "asyncio.queue.pressure.changed",
    "asyncio.queue.contention.detected",
    "asyncio.queue.saturation.detected",
)
