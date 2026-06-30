"""AsyncViz blocking-detection validation runtime.

Exercises the blocking-threshold detector, the stack-capture engine,
and the warning-emitter aggregation pipeline by intentionally
blocking the event loop in several different shapes.

Detector defaults (relevant here):

  * lag warning_seconds  = 0.05  (50 ms)
  * lag critical_seconds = 0.25  (250 ms)
  * sample interval      = 0.20  (200 ms)
  * escalation_warning_threshold  = 5 consecutive WARNING samples
  * escalation_critical_threshold = 3 consecutive CRITICAL samples

The four offender tasks below are calibrated to land in different
buckets so the dashboard shows distinct warning groups rather than a
single blur:

  * ``rapid_offender``    → 80 ms blocks every ~700 ms
        Floats just over the warning threshold. With samples cadenced
        at 200 ms, several consecutive samples should bucket into
        WARNING. Useful for verifying the warning-only escalation.
  * ``heavy_offender``    → 350 ms blocks every ~1.5 s
        Lands solidly in the CRITICAL bucket. Three of these in a
        row open a critical warning group with a captured stack.
  * ``burst_offender``    → every ~6 s, five back-to-back 220 ms
        blocks separated by tiny ``asyncio.sleep`` yields. Stresses
        the escalation lifecycle (open → escalating → active).
  * ``nested_offender``   → calls a helper which calls another helper
        that blocks 400 ms. Validates that the captured stack frame
        attribution surfaces the right function name (not the
        outermost ``asyncio.create_task`` callsite).

Run with::

    asyncviz run validation/blocking_runtime.py

Then open ``/warnings`` for the warning groups + lifecycle, and
``/timeline`` for the freeze bars that align with each call.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random

# ``asyncviz run`` executes the target via ``runpy.run_path`` which
# does not put the script's directory on ``sys.path``. Inject it so
# the sibling ``_common`` module is importable both under the CLI
# and during a standalone ``python validation/blocking_runtime.py``.
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    add_common_args,
    cancel_all,
    common_from_namespace,
    install_signal_handlers,
    setup_logging,
    wait_for_shutdown,
)

logger = logging.getLogger("validation.blocking")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Blocking-detection validation workload",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_args(parser)
    parser.add_argument(
        "--warmup",
        type=float,
        default=3.0,
        help="seconds of clean asyncio activity before blocking starts",
    )
    return parser.parse_args(argv)


async def rapid_offender(stop: asyncio.Event, rng: random.Random) -> None:
    """Block ~80 ms every ~700 ms — sits in the WARNING bucket."""
    logger.warning("rapid_offender active — expect WARNING-level blocking events")
    count = 0
    while not stop.is_set():
        count += 1
        dur = rng.uniform(0.07, 0.10)
        logger.info("rapid_offender #%s blocking %.0f ms", count, dur * 1000)
        time.sleep(dur)  # noqa: ASYNC251 — intentional
        await asyncio.sleep(rng.uniform(0.6, 0.9))


async def heavy_offender(stop: asyncio.Event, rng: random.Random) -> None:
    """Block ~350 ms every ~1.5 s — sits in the CRITICAL bucket."""
    logger.warning("heavy_offender active — expect CRITICAL blocking events")
    count = 0
    while not stop.is_set():
        count += 1
        dur = rng.uniform(0.30, 0.45)
        logger.info("heavy_offender #%s blocking %.0f ms", count, dur * 1000)
        time.sleep(dur)  # noqa: ASYNC251 — intentional
        await asyncio.sleep(rng.uniform(1.3, 1.8))


async def burst_offender(stop: asyncio.Event, rng: random.Random) -> None:
    """Five 220 ms blocks back-to-back every ~6 s.

    The yields between blocks are tiny on purpose — the detector
    samples at 200 ms cadence, so spacing the blocks tightly keeps
    the escalation counter ticking.
    """
    logger.warning("burst_offender active — expect WARNING→CRITICAL escalation groups")
    burst = 0
    while not stop.is_set():
        burst += 1
        logger.info("burst_offender burst #%s starting", burst)
        for _blk in range(5):
            time.sleep(rng.uniform(0.20, 0.25))  # noqa: ASYNC251 — intentional
            await asyncio.sleep(0.005)
            if stop.is_set():
                return
        logger.info("burst_offender burst #%s finished", burst)
        await asyncio.sleep(rng.uniform(5.0, 7.0))


async def nested_offender(stop: asyncio.Event, rng: random.Random) -> None:
    """Three call frames deep before the actual block.

    Validates that the stack-capture engine attributes the freeze
    to the leaf frame (``_inner_compute``) rather than the outer
    coroutine.
    """

    def _inner_compute(dur: float) -> int:
        # Burn CPU briefly so the stack capture sees a synchronous
        # frame in addition to the sleep call.
        accumulator = 0
        for i in range(10_000):
            accumulator += i
        time.sleep(dur)
        return accumulator

    def _middle(dur: float) -> int:
        return _inner_compute(dur)

    logger.warning("nested_offender active — expect stack-capture pointing at _inner_compute")
    count = 0
    while not stop.is_set():
        count += 1
        dur = rng.uniform(0.35, 0.55)
        logger.info("nested_offender #%s blocking %.0f ms (3 frames deep)", count, dur * 1000)
        # Call the nested chain — the patcher sees this as the
        # offending coroutine; the stack capture should walk into
        # _middle → _inner_compute.
        _middle(dur)
        await asyncio.sleep(rng.uniform(2.0, 3.0))


async def keepalive_chatter(stop: asyncio.Event) -> None:
    """Pure-async background noise.

    Gives the dashboard's timeline + event ring some non-blocking
    activity to render alongside the freezes, so the contrast is
    visible (clean stretches vs. freeze bars).
    """
    tick = 0
    while not stop.is_set():
        tick += 1
        # No work — just yield. The asyncio patcher emits task lifecycle
        # events; that's the visible contribution.
        await asyncio.sleep(0.5)


async def run_workload(args: argparse.Namespace) -> None:
    config = common_from_namespace(args)
    rng = random.Random(config.seed)
    stop = asyncio.Event()
    install_signal_handlers(stop)

    logger.info(
        "blocking validation starting: duration=%.0fs warmup=%.1fs seed=%s",
        config.duration_seconds,
        args.warmup,
        config.seed,
    )

    # Warmup chatter so the lag baseline settles before the offenders
    # start — makes the first blocking event a clean signal rather
    # than an averaged-in startup tax.
    chatter = asyncio.create_task(keepalive_chatter(stop), name="keepalive-chatter")
    if args.warmup > 0:
        try:
            await asyncio.wait_for(stop.wait(), timeout=args.warmup)
            return
        except TimeoutError:
            pass

    offenders = [
        asyncio.create_task(
            rapid_offender(stop, random.Random(rng.random())),
            name="rapid-offender",
        ),
        asyncio.create_task(
            heavy_offender(stop, random.Random(rng.random())),
            name="heavy-offender",
        ),
        asyncio.create_task(
            burst_offender(stop, random.Random(rng.random())),
            name="burst-offender",
        ),
        asyncio.create_task(
            nested_offender(stop, random.Random(rng.random())),
            name="nested-offender",
        ),
    ]

    try:
        await wait_for_shutdown(stop, config.duration_seconds - args.warmup)
    finally:
        await cancel_all([chatter, *offenders])
        logger.info("blocking validation shutdown complete")


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
