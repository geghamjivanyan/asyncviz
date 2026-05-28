from __future__ import annotations

import asyncio
import inspect

from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.metrics import EventBusMetrics
from asyncviz.runtime.events.queue import BoundedEventQueue
from asyncviz.runtime.events.subscriber import Subscription, SubscriptionRegistry
from asyncviz.utils.logging import get_logger

logger = get_logger("runtime.events.dispatcher")


class Dispatcher:
    """Owns the consumer loop that drains the queue and fans events out.

    Lives entirely on the bus's event-loop thread. Subscriber failures are
    caught here so they never escape into the dispatcher coroutine; if they
    did, ``asyncio.gather`` would propagate the first exception and stall
    subsequent events.
    """

    def __init__(
        self,
        queue: BoundedEventQueue,
        registry: SubscriptionRegistry,
        metrics: EventBusMetrics,
    ) -> None:
        self._queue = queue
        self._registry = registry
        self._metrics = metrics

    async def run(self) -> None:
        while True:
            event = await self._queue.take()
            try:
                await self._fanout(event)
            finally:
                self._queue.task_done()
            self._metrics.dispatched += 1

    async def _fanout(self, event: RuntimeEvent) -> None:
        subs = self._registry.matching(event.event_type)
        if not subs:
            return
        # Internal fanout — suppress gather instrumentation so the patched
        # gather doesn't emit ``asyncio.gather.*`` events back into the bus,
        # which would re-trigger this dispatcher and amplify endlessly.
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
            self._metrics.subscriber_failures += 1
            logger.warning("subscriber %d failed on event %r: %s", sub.id, event.event_type, exc)
