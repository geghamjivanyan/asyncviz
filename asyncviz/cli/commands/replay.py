"""``asyncviz replay`` — open a recorded ``.avz`` bundle in the dashboard.

The heavy lifting lives in :func:`asyncviz.cli.runtime.replay_launcher.run_replay`.
This command is a thin adapter that:

1. Validates the parsed config arrived (defensive — the dispatcher
   normally hands us one).
2. Delegates to :func:`run_replay`.
3. Returns its exit code unchanged.

No banner / progress logging happens here — the launcher owns that
so test paths that call ``run_replay`` directly get the same output.
"""

from __future__ import annotations

import argparse

from asyncviz.cli.configuration import ReplayCliConfig
from asyncviz.cli.exit_codes import ExitCode
from asyncviz.cli.output import error
from asyncviz.cli.runtime.replay_launcher import run_replay


def run(
    args: argparse.Namespace,
    *,
    config: ReplayCliConfig | None = None,
) -> int:
    if config is None:
        error("replay command invoked without a parsed config")
        return int(ExitCode.GENERIC_FAILURE)
    outcome = run_replay(config)
    return outcome.exit_code
