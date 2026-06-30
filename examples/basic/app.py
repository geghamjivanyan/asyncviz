"""AsyncViz · basic example.

A tiny asyncio program that lights up every page of the dashboard
with the smallest amount of code we expect from a real user.

Run it with::

    python app.py

The dashboard opens at http://127.0.0.1:8877 — leave the page open
while the program runs and watch the tasks, timeline, queues,
semaphores, dependencies, metrics, and diagnostics come to life.
Press ``Ctrl+C`` to stop.

Nothing in this file is a stress test or a microbenchmark — every
``await asyncio.sleep`` is intentional, the workload runs well
under capacity, and Diagnostics stays "Healthy" the whole time.
"""

from __future__ import annotations

import asyncio
import contextlib
import random

import asyncviz

# ── Workload ─────────────────────────────────────────────────────────────


async def heartbeat() -> None:
    """A long-lived task that ticks once per second.

    Most ticks are a plain sleep; every fifth tick the heartbeat
    does a tiny async operation so the timeline shows a varied
    rhythm instead of a perfectly flat line.
    """
    tick = 0
    while True:
        tick += 1
        await asyncio.sleep(1.0)
        if tick % 5 == 0:
            # Pretend to ping a downstream service — a short await so
            # the timeline shows a brief stripe of running activity.
            await asyncio.sleep(random.uniform(0.05, 0.15))


async def producer(queue: asyncio.Queue[int]) -> None:
    """Push jobs onto a shared queue.

    Most of the time the producer paces itself with the workers.
    Every dozen items it does a short *burst* of 3-4 quick puts to
    make the queue's occupancy oscillate visibly on the Queues
    page — but the bursts are bounded so the queue never saturates
    and Diagnostics stays clean.
    """
    counter = 0
    while True:
        counter += 1
        await queue.put(counter)
        if counter % 12 == 0:
            # Short burst — a few quick puts in a row.
            for _ in range(random.randint(2, 3)):
                counter += 1
                await queue.put(counter)
                await asyncio.sleep(0.04)
        await asyncio.sleep(random.uniform(0.25, 0.45))


async def worker(queue: asyncio.Queue[int]) -> None:
    """Pop jobs from the queue and process them.

    Each job takes 150-400 ms — long enough that the Timeline page
    shows visible running bars, short enough that the workers
    keep up with the producer with room to spare.
    """
    while True:
        await queue.get()
        try:
            # The dashboard cares about timing, not the payload —
            # this sleep stands in for whatever work the worker
            # would actually do.
            await asyncio.sleep(random.uniform(0.15, 0.40))
        finally:
            queue.task_done()


async def fetch(name: str) -> str:
    """Pretend to fetch something over the network.

    Wide variance (100-550 ms) so the children of each ``gather``
    finish at different times — that's what gives the Dependencies
    page its "fan-in / staggered completion" look.
    """
    await asyncio.sleep(random.uniform(0.10, 0.55))
    return f"{name}-ok"


async def parent_with_children() -> None:
    """A parent task that gathers a fan-out of children.

    The parent loops with only a short pause between iterations so
    successive fan-outs overlap on the timeline — you can see two
    or three "parents" worth of children running side by side.
    """
    iteration = 0
    while True:
        iteration += 1
        await asyncio.gather(
            fetch(f"db-{iteration}"),
            fetch(f"cache-{iteration}"),
            fetch(f"api-{iteration}"),
            fetch(f"auth-{iteration}"),
        )
        # Short pause so the next fan-out starts before the previous
        # one is fully off the timeline — gives the Dependencies
        # graph a steady stream of nodes to render.
        await asyncio.sleep(random.uniform(0.25, 0.55))


async def semaphore_worker(semaphore: asyncio.Semaphore) -> None:
    """Acquire a shared semaphore, do brief work, release.

    Four of these run against a semaphore with only two permits, so
    the Semaphores page shows occasional waiters without ever
    deadlocking or saturating — exactly the "healthy contention"
    pattern the page is designed to surface.
    """
    while True:
        async with semaphore:
            await asyncio.sleep(random.uniform(0.20, 0.50))
        await asyncio.sleep(random.uniform(0.15, 0.30))


async def progress_logger() -> None:
    """Emit a single concise progress line every 30 seconds.

    The dashboard is the primary view; the terminal stays quiet so
    operators can leave the program running in the background.
    """
    seconds = 0
    while True:
        await asyncio.sleep(30.0)
        seconds += 30
        print(f"… {seconds}s elapsed — dashboard at http://127.0.0.1:8877")


async def main() -> None:
    # Start AsyncViz with the defaults. This serves the dashboard
    # at http://127.0.0.1:8877, opens your default browser to it,
    # and patches asyncio so every task / queue / gather / semaphore
    # is observed automatically.
    asyncviz.start()

    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=12)
    # Two permits, four contenders — brief, healthy contention.
    semaphore = asyncio.Semaphore(2)

    tasks = [
        asyncio.create_task(heartbeat(), name="heartbeat"),
        asyncio.create_task(producer(queue), name="producer"),
        asyncio.create_task(worker(queue), name="worker-1"),
        asyncio.create_task(worker(queue), name="worker-2"),
        asyncio.create_task(parent_with_children(), name="parent"),
        asyncio.create_task(semaphore_worker(semaphore), name="sem-worker-1"),
        asyncio.create_task(semaphore_worker(semaphore), name="sem-worker-2"),
        asyncio.create_task(semaphore_worker(semaphore), name="sem-worker-3"),
        asyncio.create_task(semaphore_worker(semaphore), name="sem-worker-4"),
        asyncio.create_task(progress_logger(), name="progress"),
    ]

    print("AsyncViz is running. Open http://127.0.0.1:8877 — Ctrl+C to stop.")

    # The tasks above are cancelled cleanly during shutdown — gather()
    # surfaces that as CancelledError, which we suppress so the
    # finally-block can shut AsyncViz down without a traceback.
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down…")
    finally:
        asyncviz.stop()
