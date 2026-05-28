"""``asyncviz record`` — like ``run``, but captures a replay bundle.

The heavy lifting lives in :mod:`asyncviz.cli.runtime.launcher` — the
parser already populates :attr:`RunCliConfig.recording`, and the
subprocess bootstrap reads the env vars + starts the
:class:`ReplayRecorder`. This command is therefore a tiny wrapper
that:

1. Validates the recording configuration.
2. Prints a recording-aware banner.
3. Delegates to :func:`run_target`.
4. Prints the resulting artifact path + a one-line summary.
"""

from __future__ import annotations

import argparse

from asyncviz.cli.configuration import RunCliConfig
from asyncviz.cli.exit_codes import ExitCode
from asyncviz.cli.output import error, info, log, ok
from asyncviz.cli.runtime.launcher import run_target


def run(args: argparse.Namespace, *, config: RunCliConfig | None = None) -> int:
    if config is None:
        error("record command invoked without a parsed config")
        return int(ExitCode.GENERIC_FAILURE)
    if not config.recording.enabled or config.recording.output_path is None:
        error("record command requires recording.enabled + an output path")
        return int(ExitCode.CONFIGURATION_ERROR)

    output = config.recording.output_path
    if not config.quiet:
        log("AsyncViz · record")
        info(f"target       {config.target.kind}={config.target.display_name()}")
        info(f"bundle       {output}")
        info(f"compression  {config.recording.compression}")
        info(
            f"chunk-roll   events={config.recording.chunk_events} "
            f"bytes={config.recording.chunk_bytes}",
        )

    outcome = run_target(config)

    if not config.quiet:
        if outcome.exit_code == int(ExitCode.OK):
            ok(f"replay bundle saved at {output}")
        else:
            error(f"replay bundle (incomplete) at {output}")
    return outcome.exit_code
