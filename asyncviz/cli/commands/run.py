"""``asyncviz run`` — launch a Python target with AsyncViz attached."""

from __future__ import annotations

import argparse

from asyncviz.cli.configuration import RunCliConfig
from asyncviz.cli.exit_codes import ExitCode
from asyncviz.cli.output import error
from asyncviz.cli.runtime.launcher import run_target


def run(args: argparse.Namespace, *, config: RunCliConfig | None = None) -> int:
    """Entry point invoked by :mod:`asyncviz.cli.entrypoint`.

    ``config`` is normally derived from ``args`` by the parser. Tests
    + plugin callers can pass a hand-built config to skip argparse.
    """
    if config is None:
        error("run command invoked without a parsed config")
        return int(ExitCode.GENERIC_FAILURE)
    outcome = run_target(config)
    return outcome.exit_code
