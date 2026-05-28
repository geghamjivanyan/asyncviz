"""Queue-bridge tests."""

from __future__ import annotations

import asyncio

from asyncviz.runtime.compat import LoopQueueBridge


async def test_counters_start_at_zero() -> None:
    bridge = LoopQueueBridge()
    stats = bridge.stats()
    assert stats.queues_seen == 0
    assert stats.semaphores_seen == 0


async def test_attach_to_queue_observes_blocking_get() -> None:
    bridge = LoopQueueBridge()
    queue: asyncio.Queue[int] = asyncio.Queue()
    bridge.attach_to_queue(queue)
    getter = asyncio.create_task(queue.get())
    await asyncio.sleep(0)
    queue.put_nowait(1)
    value = await getter
    assert value == 1
    assert bridge.stats().blocking_gets >= 1


async def test_attach_to_queue_observes_blocking_put() -> None:
    bridge = LoopQueueBridge()
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
    bridge.attach_to_queue(queue)
    await queue.put(0)
    putter = asyncio.create_task(queue.put(1))
    await asyncio.sleep(0)
    assert not putter.done()
    queue.get_nowait()
    await putter
    assert bridge.stats().blocking_puts >= 1


async def test_attach_to_semaphore_observes_acquire() -> None:
    bridge = LoopQueueBridge()
    sem = asyncio.Semaphore(1)
    bridge.attach_to_semaphore(sem)
    async with sem:
        pass
    assert bridge.stats().semaphore_acquires >= 1


async def test_reset_clears_counters() -> None:
    bridge = LoopQueueBridge()
    queue: asyncio.Queue[int] = asyncio.Queue()
    bridge.attach_to_queue(queue)
    bridge.reset()
    assert bridge.stats().queues_seen == 0
