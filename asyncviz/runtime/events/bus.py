from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Iterable
from typing import TYPE_CHECKING

from asyncviz.runtime.events.dispatcher import Dispatcher
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.exceptions import EventBusNotRunningError
from asyncviz.runtime.events.metrics import EventBusMetrics, EventBusMetricsSnapshot
from asyncviz.runtime.events.queue import BoundedEventQueue
from asyncviz.runtime.events.subscriber import (
    EventCallback,
    Subscription,
    SubscriptionRegistry,
)
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.runtime.queue import InternalEventQueue

logger = get_logger("runtime.events.bus")

DEFAULT_MAXSIZE = 10_000


class EventBus:
    """In-process publish/subscribe bus for runtime events.

    Lifecycle::

        bus = EventBus()
        await bus.start()
        sub = bus.subscribe(callback, event_types={"task.created"})
        bus.publish(RuntimeEvent.of("task.created", id=1))
        await bus.stop()

    Publishing is always non-blocking. Dispatch happens asynchronously on a
    single background task that owns the consumer loop. Slow subscribers
    don't block publishers — only the dispatch tail — and a full queue
    drops the new event while incrementing :attr:`metrics.dropped`.
    """

    def __init__(self, *, maxsize: int = DEFAULT_MAXSIZE) -> None:
        self._maxsize = maxsize
        self._registry = SubscriptionRegistry()
        self._metrics = EventBusMetrics()
        self._queue: BoundedEventQueue | None = None
        self._dispatcher: Dispatcher | None = None
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False
        # When non-None, ``publish`` delegates to this queue instead of the
        # bus's own internal channel. The queue owns ordering + retention +
        # replay; the bus becomes a subscriber-fanout surface. See
        # :mod:`asyncviz.runtime.queue` for the full architecture.
        self._event_queue: InternalEventQueue | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────
    async def start(self) -> None:
        if self._running:
            return
        if self._event_queue is not None:
            # Delegating — don't spin up the bus's own dispatch loop. The
            # queue owns dispatch. We still flip ``_running`` so ``publish``
            # gates on it consistently.
            self._loop = asyncio.get_running_loop()
            self._running = True
            logger.debug("event bus started (delegating to internal event queue)")
            return
        self._queue = BoundedEventQueue(self._maxsize)
        self._dispatcher = Dispatcher(self._queue, self._registry, self._metrics)
        self._loop = asyncio.get_running_loop()
        self._dispatcher_task = asyncio.create_task(
            self._dispatcher.run(), name="asyncviz-event-bus"
        )
        self._running = True
        logger.debug("event bus started (maxsize=%d)", self._maxsize)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._dispatcher_task is not None:
            self._dispatcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._dispatcher_task
        self._dispatcher_task = None
        self._dispatcher = None
        self._queue = None
        self._loop = None
        logger.debug("event bus stopped")

    @property
    def is_running(self) -> bool:
        if self._event_queue is not None:
            return self._running and self._event_queue.is_running
        return (
            self._running and self._dispatcher_task is not None and not self._dispatcher_task.done()
        )

    # ── subscribe / unsubscribe ──────────────────────────────────────────
    def subscribe(
        self,
        callback: EventCallback,
        *,
        event_types: Iterable[str] | None = None,
    ) -> Subscription:
        """Register a callback. Pass ``event_types=None`` for a wildcard sub."""
        # If we're delegating to an :class:`InternalEventQueue`, subscriptions
        # must live in the queue's registry so its dispatcher sees them. We
        # share the same :class:`SubscriptionRegistry` instance for that
        # reason; the bus's local registry stays in sync.
        return self._registry.add(callback, event_types)

    def unsubscribe(self, subscription: Subscription) -> bool:
        """Remove a previous :meth:`subscribe` registration. Idempotent."""
        return self._registry.remove(subscription.id)

    # ── queue attachment ─────────────────────────────────────────────────
    def attach_event_queue(self, queue: InternalEventQueue) -> None:
        """Route publishes through ``queue`` and share its subscription registry.

        After attachment:
          * ``self.publish(event)`` forwards to ``queue.publish(event)``.
          * ``self.subscribe(...)`` continues to work but registers on the
            *queue*'s registry (so the queue's dispatcher fans out correctly).
          * The bus's own dispatcher loop, if running, is left alone — but
            should be stopped by the caller (we don't want two consumers).

        Must be called before ``start``, or after ``stop``. Calling on a
        running bus would create two dispatch loops fighting over the same
        registry — :class:`EventBusNotRunningError` is raised in that case.
        """
        if self._running:
            raise EventBusNotRunningError("attach_event_queue requires a stopped bus")
        self._event_queue = queue
        # Share the subscription registry with the queue so subscribers added
        # via either object are visible to both.
        self._registry = queue.registry

    def detach_event_queue(self) -> None:
        """Reverse :meth:`attach_event_queue`. Idempotent."""
        if self._running:
            raise EventBusNotRunningError("detach_event_queue requires a stopped bus")
        self._event_queue = None
        # Restore a fresh registry so post-detach subscribers don't leak into
        # whatever the queue is still using.
        self._registry = SubscriptionRegistry()

    @property
    def has_event_queue(self) -> bool:
        return self._event_queue is not None

    # ── publish ──────────────────────────────────────────────────────────
    def publish(self, event: RuntimeEvent) -> bool:
        """Enqueue ``event`` for dispatch. Never blocks.

        When an :class:`InternalEventQueue` is attached, publishes route
        through it (sequence allocation, retention, backpressure). Otherwise
        the bus's own bounded queue is used — the legacy fast path, kept for
        tests and scripts that construct a bus without a queue.

        Returns ``True`` if the event was accepted, ``False`` on overflow or
        when neither path is running.
        """
        if self._event_queue is not None:
            # Delegate. The queue records its own metrics; we still bump the
            # bus's ``published`` counter so the bus-level metric stays
            # informative for callers that look at it alone.
            accepted = self._event_queue.publish(event)
            if accepted:
                self._metrics.published += 1
            else:
                self._metrics.dropped += 1
            return accepted

        if not self._running or self._queue is None or self._loop is None:
            self._metrics.dropped += 1
            return False

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self._loop:
            return self._enqueue_local(event)

        # Cross-thread publish — schedule the enqueue on the bus's loop.
        # We can't know the per-event accept/reject result synchronously, so
        # the metric is recorded inside the scheduled callback.
        self._loop.call_soon_threadsafe(self._enqueue_local, event)
        return True

    def _enqueue_local(self, event: RuntimeEvent) -> bool:
        if self._queue is None:
            self._metrics.dropped += 1
            return False
        if self._queue.offer(event):
            self._metrics.published += 1
            return True
        self._metrics.dropped += 1
        return False

    # ── observability ────────────────────────────────────────────────────
    @property
    def metrics(self) -> EventBusMetrics:
        return self._metrics

    def metrics_snapshot(self) -> EventBusMetricsSnapshot:
        queue_size = self._queue.qsize() if self._queue is not None else 0
        return self._metrics.snapshot(
            subscriber_count=self._registry.count(),
            queue_size=queue_size,
        )

    async def join(self) -> None:
        """Wait for every enqueued event to be dispatched.

        Uses the underlying queue's ``task_done`` accounting — the dispatcher
        calls it only after fanout completes, so ``join()`` returns once
        every subscriber for every pending event has finished.
        """
        if self._event_queue is not None:
            await self._event_queue.join()
            return
        if not self._running or self._queue is None:
            raise EventBusNotRunningError("bus is not running")
        await self._queue.wait_drained()
