from __future__ import annotations

import asyncio

from asyncviz.runtime.queue.buffering import QueuedEvent


class EventChannel:
    """Thin wrapper over ``asyncio.Queue[QueuedEvent]`` with bounded semantics.

    Centralizes the put/get policy so the queue's hot path stays small and
    the overflow strategies in :mod:`asyncviz.runtime.queue.backpressure`
    have one well-defined place to apply.

    The channel does **not** decide the overflow policy itself — it surfaces
    a typed boolean ("did the put succeed?") and lets the queue act on it.
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 0:
            raise ValueError(f"capacity must be ≥ 0 (got {capacity})")
        self._capacity = capacity
        # ``asyncio.Queue(0)`` is *unbounded* in CPython — that's the wrong
        # default for us. We require an explicit positive capacity.
        if capacity == 0:
            raise ValueError("capacity must be > 0; use a large number for 'unbounded'")
        self._queue: asyncio.Queue[QueuedEvent] = asyncio.Queue(maxsize=capacity)
        # Internal AsyncViz transport: skip instrumentation. Without this
        # the bus dispatcher's get() would emit an event back through the
        # bus, re-queue itself, and live-lock the dispatch loop. Imported
        # lazily to avoid a circular import.
        from asyncviz.instrumentation.queue.queue_internal import mark_queue_internal

        mark_queue_internal(self._queue)

    @property
    def capacity(self) -> int:
        return self._capacity

    def qsize(self) -> int:
        return self._queue.qsize()

    def offer(self, item: QueuedEvent) -> bool:
        """Non-blocking put. Returns ``True`` on success, ``False`` on overflow."""
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            return False
        return True

    def take_nowait(self) -> QueuedEvent | None:
        """Non-blocking head pop. Used by overflow strategies that drop oldest."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def take(self) -> QueuedEvent:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    async def wait_drained(self) -> None:
        await self._queue.join()
