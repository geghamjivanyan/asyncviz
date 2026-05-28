from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Iterable

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.subscriber import (
    EventCallback,
    Subscription,
    SubscriptionRegistry,
)
from asyncviz.runtime.queue.backpressure import (
    DEFAULT_OVERFLOW_STRATEGY,
    OverflowStrategy,
)
from asyncviz.runtime.queue.buffering import QueuedEvent
from asyncviz.runtime.queue.channels import EventChannel
from asyncviz.runtime.queue.dispatcher import PostDispatchHook, QueueDispatcher
from asyncviz.runtime.queue.exceptions import (
    EventQueueNotRunningError,
    EventQueueOverflowError,
)
from asyncviz.runtime.queue.metrics import QueueMetrics, QueueMetricsSnapshot
from asyncviz.runtime.queue.retention import RetentionBuffer
from asyncviz.runtime.queue.snapshots import QueueSnapshotResponse, ReplayResult
from asyncviz.utils.logging import get_logger

logger = get_logger("runtime.queue.event_queue")

#: Conservative default. At 10k slots x ~500 bytes/event ~ 5 MB worst-case;
#: the dashboard's dispatcher drains it in microseconds under steady load.
DEFAULT_CAPACITY: int = 10_000

#: Default retention — enough for typical reconnect storms (browser refresh,
#: transient network blip) without bloating memory.
DEFAULT_RETENTION: int = 2_048


class InternalEventQueue:
    """Canonical event transport for an AsyncViz runtime.

    Sits between instrumentation (producers) and the :class:`EventBus`'s
    subscriber registry (consumers). Owns:

    * **Sequencing** — stamps every publish with the next clock-allocated
      sequence number; producers cannot bypass this.
    * **Bounded buffering** — backpressure via configurable
      :class:`OverflowStrategy`.
    * **Retention** — a fixed-size ring of recent :class:`QueuedEvent`\\ s
      so reconnecting clients can replay events newer than their last seen
      sequence.
    * **Dispatch** — pulls events off the channel and fans them out to
      subscribers; subscriber failures are isolated.

    Thread-safe. :meth:`publish` may be called from any thread and is
    non-blocking; cross-thread publishes are scheduled onto the bound
    asyncio loop via ``call_soon_threadsafe``.

    Lifecycle::

        queue = InternalEventQueue(clock=clock)
        await queue.start()
        queue.subscribe(callback)
        queue.publish(event)
        await queue.stop()
    """

    def __init__(
        self,
        *,
        clock: RuntimeClock | None = None,
        registry: SubscriptionRegistry | None = None,
        capacity: int = DEFAULT_CAPACITY,
        retention: int = DEFAULT_RETENTION,
        overflow: OverflowStrategy = DEFAULT_OVERFLOW_STRATEGY,
    ) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0 (got {capacity})")
        self._clock = clock or get_runtime_clock()
        self._registry = registry or SubscriptionRegistry()
        self._owns_registry = registry is None
        self._capacity = capacity
        self._retention_capacity = max(0, retention)
        self._overflow = overflow

        self._metrics = QueueMetrics()
        self._retention = RetentionBuffer(self._retention_capacity)
        self._channel: EventChannel | None = None
        self._dispatcher: QueueDispatcher | None = None
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False
        self._lifecycle_lock = threading.Lock()

    # ── lifecycle ────────────────────────────────────────────────────────
    async def start(self) -> None:
        with self._lifecycle_lock:
            if self._running:
                return
            self._channel = EventChannel(self._capacity)
            self._dispatcher = QueueDispatcher(
                self._channel,
                self._registry,
                self._retention,
                self._metrics,
            )
            self._loop = asyncio.get_running_loop()
            self._dispatcher_task = asyncio.create_task(
                self._dispatcher.run(), name="asyncviz-internal-event-queue"
            )
            self._running = True
        logger.debug(
            "internal event queue started (capacity=%d, retention=%d, overflow=%s)",
            self._capacity,
            self._retention_capacity,
            self._overflow.value,
        )

    async def stop(self) -> None:
        with self._lifecycle_lock:
            if not self._running:
                return
            self._running = False
            task = self._dispatcher_task
            self._dispatcher_task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._channel = None
        self._dispatcher = None
        self._loop = None
        logger.debug("internal event queue stopped")

    @property
    def is_running(self) -> bool:
        task = self._dispatcher_task
        return self._running and task is not None and not task.done()

    # ── subscriber API (delegates to the shared registry) ────────────────
    def subscribe(
        self,
        callback: EventCallback,
        *,
        event_types: Iterable[str] | None = None,
    ) -> Subscription:
        return self._registry.add(callback, event_types)

    def unsubscribe(self, subscription: Subscription) -> bool:
        return self._registry.remove(subscription.id)

    @property
    def registry(self) -> SubscriptionRegistry:
        return self._registry

    # ── publish ──────────────────────────────────────────────────────────
    def publish(self, event: RuntimeEvent) -> bool:
        """Stamp ``event`` with a sequence and enqueue it for dispatch.

        Returns ``True`` if the event made it onto the channel, ``False`` on
        overflow (only for ``DROP_NEWEST`` and ``DROP_OLDEST`` strategies —
        ``FAIL_FAST`` raises :class:`EventQueueOverflowError`).

        Non-blocking. Safe to call from any thread; cross-thread publishes
        are scheduled onto the bound loop via ``call_soon_threadsafe``.
        """
        if not self._running or self._channel is None or self._loop is None:
            return False

        sequence = self._clock.next_sequence()
        item = QueuedEvent(sequence=sequence, event=event)

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self._loop:
            return self._enqueue(item)

        # Cross-thread publish — record now (so the producer's view of
        # "published" doesn't depend on the loop's next tick), then schedule
        # the actual enqueue onto the bound loop.
        self._metrics.record_published()
        self._loop.call_soon_threadsafe(self._enqueue_cross_thread, item)
        return True

    def _enqueue(self, item: QueuedEvent) -> bool:
        """Local-loop enqueue. Applies the overflow strategy on contention."""
        assert self._channel is not None
        if self._channel.offer(item):
            self._metrics.record_published()
            return True
        # Channel is full — defer to strategy.
        if self._overflow == OverflowStrategy.FAIL_FAST:
            self._metrics.record_fail_fast()
            raise EventQueueOverflowError(
                f"queue is full ({self._channel.qsize()}/{self._channel.capacity})"
            )
        if self._overflow == OverflowStrategy.DROP_NEWEST:
            self._metrics.record_dropped_newest()
            return False
        # DROP_OLDEST: evict head, retry. ``task_done`` is *not* called for the
        # discarded item because the dispatcher never saw it — the queue's
        # ``unfinished_tasks`` counter must stay accurate.
        discarded = self._channel.take_nowait()
        if discarded is not None:
            self._metrics.record_dropped_oldest()
            self._channel.task_done()
        self._channel.offer(item)
        self._metrics.record_published()
        return True

    def _enqueue_cross_thread(self, item: QueuedEvent) -> None:
        """Cross-thread path. Same logic as :meth:`_enqueue` minus the publish counter."""
        if self._channel is None:
            return
        if self._channel.offer(item):
            return
        if self._overflow == OverflowStrategy.FAIL_FAST:
            # We can't propagate an exception across the threadsafe boundary;
            # record and log instead. FAIL_FAST in cross-thread mode is best
            # treated as a misconfiguration for instrumentation, but we'd
            # rather not crash the dashboard loop over it.
            self._metrics.record_fail_fast()
            logger.warning("FAIL_FAST overflow on cross-thread publish; dropping")
            return
        if self._overflow == OverflowStrategy.DROP_NEWEST:
            self._metrics.record_dropped_newest()
            return
        discarded = self._channel.take_nowait()
        if discarded is not None:
            self._metrics.record_dropped_oldest()
            self._channel.task_done()
        self._channel.offer(item)

    # ── replay / retention ───────────────────────────────────────────────
    def events_since(self, sequence: int) -> ReplayResult:
        """Return retained events with ``sequence > given``.

        ``hit=True`` means retention still covers ``sequence`` — the events
        list reconstructs everything missed since then. ``hit=False`` means
        the retention window has rolled past and the caller must fall back
        to a fresh snapshot.

        Treats ``sequence=0`` (no events seen yet) as always a hit — the
        retained window itself is the replay.
        """
        self._metrics.record_replay_request()
        oldest = self._retention.oldest_sequence
        newest = self._retention.newest_sequence
        if sequence < 0:
            sequence = 0

        # Hit conditions:
        #   * sequence == 0 (new client) — always a hit, even if retention is empty.
        #   * sequence ≥ newest — caller is already up to date, no events to return.
        #   * sequence ≥ oldest - 1 — the next missing event is still retained.
        if sequence == 0:
            hit = True
        elif newest is None:
            # No retention at all — only honor "I've seen nothing" requests.
            hit = sequence == 0
        elif sequence >= newest or (oldest is not None and sequence >= oldest - 1):
            hit = True
        else:
            hit = False

        if hit:
            items = self._retention.events_since(sequence)
            payload = [self._serialize(item) for item in items]
            self._metrics.record_replay_hit(len(payload))
        else:
            payload = []
            self._metrics.record_replay_miss()

        return ReplayResult(
            requested_sequence=sequence,
            hit=hit,
            oldest_available_sequence=oldest,
            newest_available_sequence=newest,
            events=payload,
        )

    @staticmethod
    def _serialize(item: QueuedEvent) -> dict[str, object]:
        """Materialize a retained event for transport, embedding the sequence.

        The ``sequence`` is added as a sibling field on the dict so wire
        consumers can re-stamp the envelope without re-walking the queue.
        """
        from asyncviz.runtime.events.models import to_dict

        payload = to_dict(item.event)
        payload["__sequence__"] = item.sequence  # internal hint, not part of the event schema
        return payload

    # ── observability ────────────────────────────────────────────────────
    def metrics_snapshot(self) -> QueueMetricsSnapshot:
        depth = self._channel.qsize() if self._channel is not None else 0
        return self._metrics.snapshot(
            depth=depth,
            retained=len(self._retention),
            capacity=self._capacity,
            retention_capacity=self._retention_capacity,
        )

    def snapshot(self) -> QueueSnapshotResponse:
        m = self.metrics_snapshot()
        return QueueSnapshotResponse(
            capacity=self._capacity,
            depth=m.depth,
            overflow_strategy=self._overflow.value,
            retention_capacity=self._retention_capacity,
            retained=m.retained,
            oldest_retained_sequence=self._retention.oldest_sequence,
            newest_retained_sequence=self._retention.newest_sequence,
            running=self.is_running,
            metrics={
                "published": m.published,
                "dispatched": m.dispatched,
                "dropped_overflow": m.dropped_overflow,
                "dropped_oldest": m.dropped_oldest,
                "dropped_newest": m.dropped_newest,
                "fail_fast_rejections": m.fail_fast_rejections,
                "subscriber_failures": m.subscriber_failures,
                "replay_requests": m.replay_requests,
                "replay_hits": m.replay_hits,
                "replay_misses": m.replay_misses,
                "replay_events_emitted": m.replay_events_emitted,
            },
        )

    # ── drain / join ─────────────────────────────────────────────────────
    async def join(self) -> None:
        """Wait until every published event has been dispatched."""
        if not self._running or self._channel is None:
            raise EventQueueNotRunningError("queue is not running")
        await self._channel.wait_drained()

    def set_post_dispatch_hook(self, hook: PostDispatchHook | None) -> None:
        """Hook invoked after each event is dispatched. WS bridge uses this."""
        if self._dispatcher is None:
            raise EventQueueNotRunningError("queue is not running")
        self._dispatcher.set_post_dispatch_hook(hook)
