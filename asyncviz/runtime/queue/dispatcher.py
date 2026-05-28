from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.subscriber import Subscription, SubscriptionRegistry
from asyncviz.runtime.queue.buffering import QueuedEvent
from asyncviz.runtime.queue.channels import EventChannel
from asyncviz.runtime.queue.metrics import QueueMetrics
from asyncviz.runtime.queue.retention import RetentionBuffer
from asyncviz.utils.logging import get_logger

logger = get_logger("runtime.queue.dispatcher")

#: Hook invoked once per :class:`QueuedEvent` *after* it has been fanned out
#: to all subscribers. The websocket bridge installs one here so it knows the
#: exact sequence each retained event got — without piggy-backing on the
#: subscription protocol.
PostDispatchHook = Callable[[QueuedEvent], Awaitable[None] | None]


class QueueDispatcher:
    """Pulls :class:`QueuedEvent`\\ s off the channel and fans them out.

    Pipeline per item:

      1. Pop one ``QueuedEvent`` from the channel.
      2. Append to the retention buffer (so reconnect replay sees it).
      3. Resolve matching subscribers via :class:`SubscriptionRegistry`.
      4. Invoke each subscriber, isolating exceptions per-subscriber.
      5. Run the optional post-dispatch hook.
      6. Update metrics.

    The dispatcher is the **single writer** to the retention buffer — that
    keeps the retention/dispatch order trivially identical. Subscribers see
    plain :class:`RuntimeEvent`\\ s; the sequence stays in ``QueuedEvent``
    so it can't be tampered with downstream.
    """

    def __init__(
        self,
        channel: EventChannel,
        registry: SubscriptionRegistry,
        retention: RetentionBuffer,
        metrics: QueueMetrics,
        *,
        post_dispatch: PostDispatchHook | None = None,
    ) -> None:
        self._channel = channel
        self._registry = registry
        self._retention = retention
        self._metrics = metrics
        self._post_dispatch = post_dispatch

    def set_post_dispatch_hook(self, hook: PostDispatchHook | None) -> None:
        """Install / replace the post-dispatch hook. Tests use this to observe."""
        self._post_dispatch = hook

    async def run(self) -> None:
        while True:
            item = await self._channel.take()
            try:
                # Retention BEFORE fanout so a slow subscriber can't delay the
                # availability of an event for reconnect replay. The reconnect
                # path doesn't need the subscriber to have finished — it just
                # needs the event recorded in the right order.
                self._retention.append(item)
                await self._fanout(item.event)
                await self._run_post_dispatch(item)
            finally:
                self._channel.task_done()
                self._metrics.record_dispatched()

    async def _fanout(self, event: RuntimeEvent) -> None:
        subs = self._registry.matching(event.event_type)
        if not subs:
            return
        # Internal fanout — suppress gather instrumentation. Same rationale
        # as the bus dispatcher (see asyncviz.runtime.events.dispatcher).
        from asyncviz.instrumentation.gather import suppress_gather_instrumentation

        with suppress_gather_instrumentation():
            await asyncio.gather(*(self._invoke(sub, event) for sub in subs))

    async def _invoke(self, sub: Subscription, event: RuntimeEvent) -> None:
        try:
            result = sub.callback(event)
            if inspect.isawaitable(result):
                await result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._metrics.record_subscriber_failure()
            logger.warning("subscriber %d failed on event %r: %s", sub.id, event.event_type, exc)

    async def _run_post_dispatch(self, item: QueuedEvent) -> None:
        if self._post_dispatch is None:
            return
        try:
            result = self._post_dispatch(item)
            if inspect.isawaitable(result):
                await result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Hooks are best-effort observability; don't poison the loop.
            logger.warning("post-dispatch hook failed for seq=%d: %s", item.sequence, exc)
