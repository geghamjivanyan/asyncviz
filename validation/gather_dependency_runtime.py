"""AsyncViz gather + dependency-graph validation runtime.

Exercises :class:`GatherInstrumentationEngine` and the task-lineage
projections. Builds three- and four-level deep ``asyncio.gather``
trees so the dashboard's Dependencies / lineage view has a real
topology to render instead of a flat list of leaf tasks.

Coverage by section:

  * **Wide fanout**       — one parent gathers 12 children with
    varied durations so stragglers are visible against fast
    siblings.
  * **Nested tree**       — root → 3 branches → 4 leaves each
    (12 leaves, 16 tasks total). Verifies parent/child linkage at
    each level and that lineage depth is reported accurately.
  * **Cascading cancel**  — every ~15 s one branch's gather is
    cancelled mid-flight, which cancels its children, which
    cancels their grand-children. Validates that the gather-cancel
    event flows through the bridge with the correct task ids.
  * **Sibling-await**     — leaf coroutines that await each other
    via a small ``asyncio.Event`` rendezvous. Exposes whether the
    dependency view tracks intra-fanout sync (it should appear as
    extra waiting edges, not as missing tasks).

Run with::

    asyncviz run validation/gather_dependency_runtime.py

Open ``/dependencies`` to see the tree; open ``/timeline`` to see
the staggered leaf completions.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random

# ``asyncviz run`` executes the target via ``runpy.run_path`` — inject
# the script's directory so the sibling ``_common`` module imports.
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    add_common_args,
    cancel_all,
    common_from_namespace,
    install_signal_handlers,
    setup_logging,
    wait_for_shutdown,
)

logger = logging.getLogger("validation.gather")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gather / dependency-graph validation workload",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_args(parser)
    parser.add_argument("--fanout-width", type=int, default=12, help="children per wide-fanout cycle")
    parser.add_argument("--tree-branches", type=int, default=3, help="root → N branches")
    parser.add_argument("--tree-leaves", type=int, default=4, help="branch → M leaves")
    parser.add_argument(
        "--cancel-every",
        type=float,
        default=15.0,
        help="seconds between cascading-cancel demos (0 to disable)",
    )
    return parser.parse_args(argv)


async def leaf(idx: int, rng: random.Random) -> int:
    await asyncio.sleep(rng.uniform(0.05, 0.40))
    return idx


async def branch(branch_idx: int, leaves: int, rng: random.Random) -> list[int]:
    """One mid-level node gathering its leaves."""
    results = await asyncio.gather(
        *(
            asyncio.create_task(leaf(branch_idx * 100 + j, rng), name=f"leaf-{branch_idx}-{j}")
            for j in range(leaves)
        )
    )
    return results


async def wide_fanout_cycle(width: int, rng: random.Random, iteration: int) -> None:
    """One parent → ``width`` children. Verifies single-level gather instrumentation."""
    logger.info("wide-fanout #%s starting (width=%s)", iteration, width)
    results = await asyncio.gather(
        *(
            asyncio.create_task(
                leaf(iteration * 1000 + j, rng),
                name=f"wide-{iteration}-{j}",
            )
            for j in range(width)
        )
    )
    logger.info("wide-fanout #%s complete (%s leaves)", iteration, len(results))


async def nested_tree_cycle(branches: int, leaves: int, rng: random.Random, iteration: int) -> None:
    """root → N branches → M leaves. The lineage view should show depth=2 nodes."""
    logger.info("nested-tree #%s starting (%sx%s)", iteration, branches, leaves)
    branch_results = await asyncio.gather(
        *(
            asyncio.create_task(branch(b, leaves, rng), name=f"branch-{iteration}-{b}")
            for b in range(branches)
        )
    )
    logger.info(
        "nested-tree #%s complete (%s branches, %s leaves total)",
        iteration,
        len(branch_results),
        sum(len(r) for r in branch_results),
    )


async def cascading_cancel_cycle(rng: random.Random, iteration: int) -> None:
    """Start a 3-level gather then cancel its root mid-flight.

    The cancel propagates through the gather to each child task. The
    dashboard's dependency view should show every cancelled task tied
    back to the original cancellation origin.
    """

    async def slow_leaf(name: str) -> str:
        await asyncio.sleep(rng.uniform(0.8, 1.2))
        return name

    async def slow_branch(branch_name: str) -> list[str]:
        return await asyncio.gather(
            *(
                asyncio.create_task(slow_leaf(f"{branch_name}.l{i}"), name=f"{branch_name}.l{i}")
                for i in range(4)
            )
        )

    logger.info("cascading-cancel #%s starting", iteration)
    # ``asyncio.gather`` returns a Future, not a coroutine — keep the
    # handle directly and cancel via ``.cancel()`` rather than wrapping
    # in ``create_task`` (which only accepts coroutines).
    root = asyncio.gather(
        *(
            asyncio.create_task(slow_branch(f"cc{iteration}.b{i}"), name=f"cc{iteration}.b{i}")
            for i in range(3)
        ),
    )
    # Give the children time to start, then cancel the root.
    await asyncio.sleep(0.3)
    logger.info("cascading-cancel #%s cancelling root (12 leaves should also cancel)", iteration)
    root.cancel()
    try:
        await root
    except asyncio.CancelledError:
        logger.info("cascading-cancel #%s cancelled cleanly", iteration)


async def sibling_await_cycle(rng: random.Random, iteration: int) -> None:
    """Children inside a fanout await each other via an Event.

    Verifies that the dashboard renders waiting edges between siblings
    of the same gather, not just parent→child edges.
    """
    ready = asyncio.Event()

    async def producer() -> None:
        await asyncio.sleep(rng.uniform(0.1, 0.3))
        logger.info("sibling-await #%s producer signaling", iteration)
        ready.set()

    async def consumer(i: int) -> int:
        await ready.wait()
        await asyncio.sleep(rng.uniform(0.02, 0.10))
        return i

    results = await asyncio.gather(
        asyncio.create_task(producer(), name=f"sib{iteration}-producer"),
        *(
            asyncio.create_task(consumer(i), name=f"sib{iteration}-consumer-{i}")
            for i in range(4)
        ),
    )
    logger.info("sibling-await #%s complete (consumers got: %s)", iteration, results[1:])


async def orchestrator(args: argparse.Namespace, stop: asyncio.Event) -> None:
    rng = random.Random(args.seed)
    iteration = 0
    last_cancel = 0.0
    loop = asyncio.get_running_loop()
    while not stop.is_set():
        iteration += 1
        # Rotate through the four patterns so each shows up multiple
        # times during a 90-second observation window.
        choice = iteration % 4
        if choice == 0:
            await wide_fanout_cycle(args.fanout_width, rng, iteration)
        elif choice == 1:
            await nested_tree_cycle(args.tree_branches, args.tree_leaves, rng, iteration)
        elif choice == 2:
            await sibling_await_cycle(rng, iteration)
        else:
            now = loop.time()
            if args.cancel_every > 0 and now - last_cancel >= args.cancel_every:
                last_cancel = now
                await cascading_cancel_cycle(rng, iteration)
            else:
                await wide_fanout_cycle(args.fanout_width // 2, rng, iteration)
        # Short idle between cycles so the timeline has gaps.
        await asyncio.sleep(rng.uniform(0.4, 1.2))


async def run_workload(args: argparse.Namespace) -> None:
    config = common_from_namespace(args)
    stop = asyncio.Event()
    install_signal_handlers(stop)
    logger.info(
        "gather/dependency validation starting: duration=%.0fs fanout=%s tree=%sx%s",
        config.duration_seconds,
        args.fanout_width,
        args.tree_branches,
        args.tree_leaves,
    )
    runner = asyncio.create_task(orchestrator(args, stop), name="gather-orchestrator")
    try:
        await wait_for_shutdown(stop, config.duration_seconds)
    finally:
        await cancel_all([runner])
        logger.info("gather/dependency validation shutdown complete")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(common_from_namespace(args))
    try:
        asyncio.run(run_workload(args))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
