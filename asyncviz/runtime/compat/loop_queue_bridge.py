"""Queue / semaphore compatibility bridge.

uvloop reimplements neither :class:`asyncio.Queue` nor
:class:`asyncio.Semaphore` — they live in pure Python and use the
loop's ``call_soon``/``call_later`` underneath. So compatibility is
near-trivial; the bridge exists primarily for *observability* (so
the diagnostics can answer "did the queue/semaphore primitives
behave the same way under uvloop?") and to provide a single seam
for future bridge implementations that may need adapter code.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueueBridgeStats:
    queues_seen: int
    semaphores_seen: int
    blocking_puts: int
    blocking_gets: int
    semaphore_acquires: int


class LoopQueueBridge:
    """Aggregate counters for queue + semaphore behavior."""

    __slots__ = (
        "_blocking_gets",
        "_blocking_puts",
        "_lock",
        "_queues_seen",
        "_semaphore_acquires",
        "_semaphores_seen",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues_seen = 0
        self._semaphores_seen = 0
        self._blocking_puts = 0
        self._blocking_gets = 0
        self._semaphore_acquires = 0

    def record_queue_created(self) -> None:
        with self._lock:
            self._queues_seen += 1

    def record_semaphore_created(self) -> None:
        with self._lock:
            self._semaphores_seen += 1

    def record_blocking_put(self) -> None:
        with self._lock:
            self._blocking_puts += 1

    def record_blocking_get(self) -> None:
        with self._lock:
            self._blocking_gets += 1

    def record_semaphore_acquire(self) -> None:
        with self._lock:
            self._semaphore_acquires += 1

    def attach_to_queue(self, queue: asyncio.Queue) -> None:
        """Hook the bridge into an existing queue so blocking ``put``/
        ``get`` calls are observed. The hook is *additive*: we don't
        rewrite the queue's behavior, we just count the calls."""
        original_put = queue.put
        original_get = queue.get

        async def _put_with_hook(item: object) -> None:
            full = queue.full()
            if full:
                self.record_blocking_put()
            await original_put(item)

        async def _get_with_hook() -> object:
            empty = queue.empty()
            if empty:
                self.record_blocking_get()
            return await original_get()

        # ``asyncio.Queue.put``/``get`` are bound methods; we replace
        # them on the *instance*, which is supported by Python's
        # descriptor protocol.
        queue.put = _put_with_hook  # type: ignore[method-assign]
        queue.get = _get_with_hook  # type: ignore[method-assign]
        self.record_queue_created()

    def attach_to_semaphore(self, semaphore: asyncio.Semaphore) -> None:
        original_acquire = semaphore.acquire

        async def _acquire_with_hook() -> bool:
            self.record_semaphore_acquire()
            return await original_acquire()

        semaphore.acquire = _acquire_with_hook  # type: ignore[method-assign]
        self.record_semaphore_created()

    def stats(self) -> QueueBridgeStats:
        with self._lock:
            return QueueBridgeStats(
                queues_seen=self._queues_seen,
                semaphores_seen=self._semaphores_seen,
                blocking_puts=self._blocking_puts,
                blocking_gets=self._blocking_gets,
                semaphore_acquires=self._semaphore_acquires,
            )

    def reset(self) -> None:
        with self._lock:
            self._queues_seen = 0
            self._semaphores_seen = 0
            self._blocking_puts = 0
            self._blocking_gets = 0
            self._semaphore_acquires = 0
