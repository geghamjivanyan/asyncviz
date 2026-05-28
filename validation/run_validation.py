#!/usr/bin/env python3
"""Launcher for the AsyncViz validation runtimes.

Lists the available scripts and launches a selected one via
``asyncviz run`` so the dashboard is attached automatically.

Usage::

    python validation/run_validation.py --list
    python validation/run_validation.py blocking
    python validation/run_validation.py queue_stress -- --duration 60
    python validation/run_validation.py mega -- --duration 180 --disable-blocking

Arguments after ``--`` are forwarded to the runtime script. The
launcher itself owns ``--list``, ``--no-asyncviz`` (for running the
script directly without the dashboard), and ``--print-cmd`` (dry-run
prints the command it would execute).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VALIDATION_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class Runtime:
    name: str
    filename: str
    summary: str
    recommended_duration: int


RUNTIMES: tuple[Runtime, ...] = (
    Runtime(
        "blocking",
        "blocking_runtime.py",
        "Aggressive blocking-detector validation (warning + critical groups, stack capture).",
        90,
    ),
    Runtime(
        "gather",
        "gather_dependency_runtime.py",
        "Nested gather trees, fanout/fanin, cascading cancellation.",
        90,
    ),
    Runtime(
        "queue",
        "queue_stress_runtime.py",
        "Bounded queues — saturation, backpressure, starvation, contention.",
        90,
    ),
    Runtime(
        "executor",
        "executor_runtime.py",
        "ThreadPool + ProcessPool — saturation, mixed scheduling.",
        90,
    ),
    Runtime(
        "semaphore",
        "semaphore_runtime.py",
        "Semaphore contention, starvation, fairness, wait cancellation.",
        90,
    ),
    Runtime(
        "mega",
        "mega_runtime.py",
        "Full-system integration — every panel populated simultaneously.",
        180,
    ),
)


def _runtime_by_name(name: str) -> Runtime | None:
    for r in RUNTIMES:
        if r.name == name or r.filename == name or r.filename == f"{name}.py":
            return r
    return None


def _print_list() -> None:
    print("Available validation runtimes:\n")
    name_width = max(len(r.name) for r in RUNTIMES)
    for r in RUNTIMES:
        print(f"  {r.name:<{name_width}}  {r.summary}")
        print(f"  {' ' * name_width}  (recommended --duration: {r.recommended_duration}s)")
    print(
        "\nLaunch with:  python validation/run_validation.py <name> [-- <extra args>]\n"
        "Examples:\n"
        "  python validation/run_validation.py blocking\n"
        "  python validation/run_validation.py queue -- --duration 60\n"
        "  python validation/run_validation.py mega -- --duration 240 --disable-blocking\n",
    )


def _build_command(runtime: Runtime, forwarded: list[str], *, use_asyncviz: bool) -> list[str]:
    target = str(VALIDATION_DIR / runtime.filename)
    if use_asyncviz:
        # ``asyncviz`` is the installed CLI; if it isn't on PATH the
        # launcher falls back to ``python -m asyncviz`` which the
        # package exposes.
        if shutil.which("asyncviz") is not None:
            return ["asyncviz", "run", target, *(["--", *forwarded] if forwarded else [])]
        return [
            sys.executable,
            "-m",
            "asyncviz",
            "run",
            target,
            *(["--", *forwarded] if forwarded else []),
        ]
    # Direct run — no dashboard. Useful for verifying the runtime
    # script itself is well-formed without spinning up the full stack.
    return [sys.executable, target, *forwarded]


def main(argv: list[str] | None = None) -> int:
    # Split off forwarded args before argparse sees them — anything
    # after a literal ``--`` goes to the runtime, not the launcher.
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    forwarded: list[str] = []
    if "--" in raw_argv:
        idx = raw_argv.index("--")
        forwarded = raw_argv[idx + 1 :]
        raw_argv = raw_argv[:idx]

    parser = argparse.ArgumentParser(
        description="AsyncViz validation runtime launcher",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Forward extra args to the runtime by placing them after '--'.",
    )
    parser.add_argument(
        "runtime",
        nargs="?",
        help="runtime name (one of: " + ", ".join(r.name for r in RUNTIMES) + ")",
    )
    parser.add_argument("--list", action="store_true", help="list available runtimes + exit")
    parser.add_argument(
        "--no-asyncviz",
        action="store_true",
        help="run the script directly via python instead of through `asyncviz run`",
    )
    parser.add_argument(
        "--print-cmd",
        action="store_true",
        help="print the command that would be executed and exit (dry run)",
    )
    args = parser.parse_args(raw_argv)

    if args.list or args.runtime is None:
        _print_list()
        return 0 if args.list else 1

    runtime = _runtime_by_name(args.runtime)
    if runtime is None:
        print(f"unknown runtime: {args.runtime}", file=sys.stderr)
        print("--- available runtimes ---", file=sys.stderr)
        _print_list()
        return 2

    command = _build_command(runtime, forwarded, use_asyncviz=not args.no_asyncviz)
    if args.print_cmd:
        print(" ".join(command))
        return 0

    print(f"→ launching '{runtime.name}' (recommended --duration {runtime.recommended_duration}s)")
    print(f"→ command: {' '.join(command)}")
    try:
        completed = subprocess.run(command, check=False)
    except FileNotFoundError as exc:
        print(f"failed to launch: {exc}", file=sys.stderr)
        return 127
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
