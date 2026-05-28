from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.dashboard.state.metrics_state import MetricsState
from asyncviz.dashboard.websocket.manager import ConnectionManager
from asyncviz.dashboard.websocket.protocol import (
    Envelope,
    runtime_event,
    runtime_snapshot,
)
from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.events import EventBus, RuntimeEvent, Subscription
from asyncviz.runtime.events.models import to_dict
from asyncviz.runtime.queue import InternalEventQueue, QueuedEvent, ReplayResult
from asyncviz.runtime.state import RuntimeStateStore
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.utils.logging import get_logger

logger = get_logger("dashboard.websocket.bridge")


@dataclass(slots=True)
class BridgeMetrics:
    """Bridge-local counters. Read via :meth:`WebSocketBridge.snapshot`."""

    forwarded: int = 0
    dropped: int = 0
    serialization_failures: int = 0
    snapshots_emitted: int = 0
    replays_emitted: int = 0
    replay_events_streamed: int = 0


class WebSocketBridge:
    """Wire mirror of the runtime's :class:`InternalEventQueue`.

    The bridge is the only producer of ordered ``runtime_event`` envelopes
    on the websocket stream. Two attachment modes:

    * **Queue mode (default in the dashboard)** — the bridge installs itself
      as the queue's *post-dispatch hook*. It receives :class:`QueuedEvent`
      values directly, so the envelope ``sequence`` matches *exactly* the
      sequence the queue retained. No re-allocation, no drift.
    * **Bus-only mode (tests + legacy)** — the bridge subscribes wildcard
      to the bus and allocates its own sequence from the clock. Sequences
      stay strictly increasing but live only on the wire.

    Lifecycle is driven by the dashboard lifespan:

      * ``await bridge.start()`` after the queue + bus are up.
      * ``await bridge.stop()``  before they tear down.
    """

    def __init__(
        self,
        event_bus: EventBus,
        manager: ConnectionManager,
        metrics_state: MetricsState,
        *,
        clock: RuntimeClock | None = None,
        event_queue: InternalEventQueue | None = None,
        state_store: RuntimeStateStore | None = None,
    ) -> None:
        self._bus = event_bus
        self._manager = manager
        self._metrics_state = metrics_state
        self._clock = clock or get_runtime_clock()
        self._event_queue = event_queue
        self._state_store = state_store
        self._lock = threading.Lock()
        self._subscription: Subscription | None = None
        self._hook_installed = False
        self._metrics = BridgeMetrics()

    async def start(self) -> None:
        with self._lock:
            if self._subscription is not None or self._hook_installed:
                return
            if self._event_queue is not None:
                # Queue mode: hook directly into the dispatcher so we see the
                # already-allocated sequence on every event.
                self._event_queue.set_post_dispatch_hook(self._forward_queued)
                self._hook_installed = True
                logger.debug("websocket bridge attached as queue post-dispatch hook")
            else:
                self._subscription = self._bus.subscribe(self._forward)
                logger.debug("websocket bridge subscribed to bus (no queue)")

    async def stop(self) -> None:
        with self._lock:
            sub = self._subscription
            self._subscription = None
            hook_installed = self._hook_installed
            self._hook_installed = False
        if sub is not None:
            self._bus.unsubscribe(sub)
            logger.debug("websocket bridge unsubscribed from bus")
        if hook_installed and self._event_queue is not None and self._event_queue.is_running:
            self._event_queue.set_post_dispatch_hook(None)
            logger.debug("websocket bridge detached from queue hook")

    @property
    def is_running(self) -> bool:
        return self._subscription is not None or self._hook_installed

    @property
    def metrics(self) -> BridgeMetrics:
        return self._metrics

    @property
    def current_sequence(self) -> int:
        return self._clock.current_sequence

    @property
    def clock(self) -> RuntimeClock:
        return self._clock

    @property
    def event_queue(self) -> InternalEventQueue | None:
        return self._event_queue

    def capture_snapshot(self, registry: TaskRegistry) -> Envelope:
        """Atomically pair (last_sequence, registry snapshot) for a new client.

        Acquires the bridge lock so any in-flight broadcast finishes (and
        allocates its envelope sequence) before the snapshot is taken. The
        snapshot's ``last_sequence`` is therefore the sequence of the **last**
        event the snapshot already reflects.
        """
        with self._lock:
            last_sequence = self._clock.current_sequence
            tasks = [snap.model_dump(mode="json") for snap in registry.snapshot_all_tasks()]
            metrics = registry.metrics_snapshot()
            lineage_metrics = registry.lineage_metrics_snapshot()
            state_metrics = (
                self._state_store.metrics_snapshot() if self._state_store is not None else None
            )
        clock_snapshot = self._clock.snapshot()
        queue_snapshot = (
            self._event_queue.snapshot().model_dump(mode="json")
            if self._event_queue is not None
            else None
        )
        state_snapshot_payload = (
            self._state_store.snapshot(include_projections=False).model_dump(mode="json")
            if self._state_store is not None
            else None
        )
        envelope = runtime_snapshot(
            last_sequence=last_sequence,
            tasks=tasks,
            metrics={
                "total_tasks": metrics.total_tasks,
                "active_tasks": metrics.active_tasks,
                "completed_tasks": metrics.completed_tasks,
                "cancelled_tasks": metrics.cancelled_tasks,
                "failed_tasks": metrics.failed_tasks,
                "terminal_tasks": metrics.terminal_tasks,
                "average_duration_seconds": metrics.average_duration_seconds,
                "cancellations_by_origin": dict(metrics.cancellations_by_origin),
                "rejected_transitions": metrics.rejected_transitions,
                "runtime_uptime_seconds": clock_snapshot.uptime_seconds,
                "sequence_issued": clock_snapshot.current_sequence,
                "lineage_tracked_tasks": lineage_metrics.tracked_tasks,
                "lineage_root_tasks": lineage_metrics.root_tasks,
                "lineage_max_depth": lineage_metrics.max_depth,
                "lineage_orphan_links": lineage_metrics.orphan_links,
                "lineage_cyclic_rejections": lineage_metrics.cyclic_rejections,
                "state_events_applied": state_metrics.events_applied
                if state_metrics is not None
                else 0,
                "state_last_sequence": state_metrics.last_event_sequence
                if state_metrics is not None
                else 0,
            },
            clock=clock_snapshot.model_dump(mode="json"),
            queue=queue_snapshot,
            state=state_snapshot_payload,
        )
        self._metrics.snapshots_emitted += 1
        return envelope

    def request_replay(self, since_sequence: int) -> ReplayResult | None:
        """Look up events newer than ``since_sequence`` in queue retention.

        Returns ``None`` when the bridge isn't in queue mode (no retention).
        The result indicates whether the replay was a *hit* (events list is
        the gap) or a *miss* (caller must fall back to a full snapshot).
        """
        if self._event_queue is None:
            return None
        return self._event_queue.events_since(since_sequence)

    async def stream_replay(self, client_send_text, result: ReplayResult) -> int:
        """Stream replayed events to one connecting client.

        ``client_send_text`` is the per-client coroutine (typically
        ``client.send_text``). Returns the number of envelopes sent so the
        caller can update metrics.
        """
        sent = 0
        for payload in result.events:
            sequence = payload.pop("__sequence__", None)
            envelope = runtime_event(payload, sequence=sequence)
            try:
                await client_send_text(envelope.model_dump_json())
            except Exception as exc:
                logger.warning("replay send failed for seq=%s: %s", sequence, exc)
                break
            sent += 1
        if sent:
            self._metrics.replays_emitted += 1
            self._metrics.replay_events_streamed += sent
        return sent

    # ── dispatch paths ───────────────────────────────────────────────────
    async def _forward_queued(self, item: QueuedEvent) -> None:
        """Queue mode: the sequence already lives on the QueuedEvent.

        We also drive the :class:`RuntimeStateStore` from here so the store
        sees the same sequence the wire envelope carries — that's how
        per-task transition history ends up with non-null sequences. The
        store is internally synchronized; this call is the *only* place
        events reach it in queue mode.
        """
        if self._state_store is not None:
            try:
                self._state_store.apply_queued(item)
            except Exception as exc:
                logger.warning(
                    "state store apply failed for %r (seq=%d): %s",
                    item.event.event_type,
                    item.sequence,
                    exc,
                )

        try:
            payload = to_dict(item.event)
        except Exception as exc:
            self._metrics.serialization_failures += 1
            logger.warning(
                "failed to serialize event %r for websocket bridge: %s",
                item.event.event_type,
                exc,
            )
            return
        envelope = runtime_event(payload, sequence=item.sequence)
        await self._broadcast(envelope, item.event.event_type)

    async def _forward(self, event: RuntimeEvent) -> None:
        """Bus-only mode: allocate the wire sequence directly from the clock."""
        try:
            payload = to_dict(event)
        except Exception as exc:
            self._metrics.serialization_failures += 1
            logger.warning(
                "failed to serialize event %r for websocket bridge: %s",
                event.event_type,
                exc,
            )
            return
        with self._lock:
            seq = self._clock.next_sequence()
        envelope = runtime_event(payload, sequence=seq)
        await self._broadcast(envelope, event.event_type)

    async def _broadcast(self, envelope: Envelope, event_type: str) -> None:
        try:
            delivered = await self._manager.broadcast(envelope)
        except Exception as exc:
            self._metrics.dropped += 1
            logger.warning("bridge broadcast failed for %r: %s", event_type, exc)
            return
        if delivered:
            self._metrics.forwarded += delivered
            self._metrics_state.inc_ws_messages(delivered)
