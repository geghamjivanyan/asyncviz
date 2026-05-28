"""Shared helpers for the AsyncViz validation runtimes.

Every script in ``validation/`` follows the same skeleton:

    config = parse_common_args(...)
    setup_logging(config)
    asyncio.run(run_workload(config))

The helpers here own the parts that would otherwise be copy-pasted —
argparse defaults, logging configuration, signal-handled stop event,
and a graceful task cancellation routine. The runtime-specific logic
lives in the individual scripts; that's where the dashboard
observability story is told.

None of these helpers import :mod:`asyncviz` — the CLI bootstrap
(``asyncviz run validation/<script>.py``) attaches the instrumentation
before the script's code executes, so every spawned task is captured
through the same channels as user code.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import sys
from collections.abc import Iterable
from dataclasses import dataclass

logger = logging.getLogger("validation")


@dataclass(frozen=True, slots=True)
class CommonConfig:
    duration_seconds: float
    seed: int
    log_level: str


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Attach the ``--duration / --seed / --log-level`` triplet."""
    parser.add_argument(
        "--duration",
        type=float,
        default=90.0,
        help="seconds to run before initiating graceful shutdown",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="seed for randomized timings (deterministic re-runs)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="root logger level",
    )


def common_from_namespace(args: argparse.Namespace) -> CommonConfig:
    return CommonConfig(
        duration_seconds=max(1.0, args.duration),
        seed=args.seed,
        log_level=args.log_level,
    )


def setup_logging(config: CommonConfig) -> None:
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


def install_signal_handlers(stop: asyncio.Event) -> None:
    """Wire SIGINT / SIGTERM to a shutdown :class:`asyncio.Event`.

    ``add_signal_handler`` is unsupported on Windows under the
    ProactorEventLoop; the suppress block tolerates that. On Unix the
    handler sets the event so the workload exits the
    ``wait_for(stop.wait(), timeout=duration)`` loop on either an
    operator Ctrl-C or the duration expiring.
    """
    loop = asyncio.get_running_loop()

    def _handler() -> None:
        if not stop.is_set():
            logger.info("signal received — initiating graceful shutdown")
            stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, _handler)


async def cancel_all(tasks: Iterable[asyncio.Task[object]]) -> None:
    """Cancel + await a group of tasks, swallowing CancelledError.

    Re-raises any non-cancellation exception via ``logger.exception``
    so debugging is straightforward, but does not propagate — a
    validation runtime that survives an internal exception is more
    useful than one that crashes mid-observation.
    """
    pending = [t for t in tasks if not t.done()]
    for task in pending:
        task.cancel()
    results = await asyncio.gather(*pending, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
            logger.exception("task ended with exception", exc_info=result)


async def wait_for_shutdown(stop: asyncio.Event, duration_seconds: float) -> None:
    """Block until ``stop`` fires or ``duration_seconds`` elapses."""
    try:
        await asyncio.wait_for(stop.wait(), timeout=duration_seconds)
    except TimeoutError:
        logger.info("duration elapsed — signaling shutdown")
        stop.set()
