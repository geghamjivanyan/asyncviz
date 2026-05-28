from __future__ import annotations

import asyncio

from asyncviz.runtime.events.event import RuntimeEvent


class BoundedEventQueue:
    """Thin wrapper over ``asyncio.Queue`` that exposes drop semantics.

    The wrapper is intentionally minimal — it just centralizes the bounded
    enqueue policy so the bus's call sites stay short and testable.
    """

    def __init__(self, maxsize: int) -> None:
        if maxsize < 0:
            raise ValueError(f"maxsize must be >= 0 (got {maxsize})")
        self._queue: asyncio.Queue[RuntimeEvent] = asyncio.Queue(maxsize=maxsize)
        # Internal AsyncViz transport: skip instrumentation so the bus
        # never recurses through the patched put/get. Imported lazily to
        # avoid a circular import (asyncviz.instrumentation → runtime.events).
        from asyncviz.instrumentation.queue.queue_internal import mark_queue_internal

        mark_queue_internal(self._queue)

    def offer(self, event: RuntimeEvent) -> bool:
        """Best-effort enqueue. Returns ``True`` on success, ``False`` on overflow."""
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            return False
        return True

    async def take(self) -> RuntimeEvent:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    async def wait_drained(self) -> None:
        """Block until every enqueued event has had ``task_done`` called."""
        await self._queue.join()

    def qsize(self) -> int:
        return self._queue.qsize()

    @property
    def maxsize(self) -> int:
        return self._queue.maxsize
