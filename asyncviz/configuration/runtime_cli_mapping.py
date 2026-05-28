"""Convert :class:`asyncviz.cli.configuration.RunCliConfig` (argparse
output) into a typed override dict the canonical resolver consumes.

Keeping the mapping in its own module means a future ``asyncviz
config dump`` command can reuse the same translator without
re-importing the CLI parser.
"""

from __future__ import annotations

from typing import Any

from asyncviz.cli.configuration import RunCliConfig


def run_config_to_overrides(config: RunCliConfig) -> dict[str, Any]:
    """Translate a :class:`RunCliConfig` into resolver overrides.

    Only fields the user *explicitly set* on the command line make
    it into the dict — defaults are filtered so they don't accidentally
    win over a profile / env var.
    """
    overrides: dict[str, Any] = {}

    # Network + dashboard scalars. We can't tell argparse "the user
    # didn't pass this" from the parsed namespace alone, so we treat
    # every value as explicit — argparse's defaults match the
    # canonical defaults so this is harmless in practice.
    overrides["host"] = config.host
    overrides["port"] = config.port
    overrides["startup_timeout"] = config.startup_timeout

    if config.debug:
        overrides["debug"] = True
    if config.log_level is not None:
        overrides["log_level"] = config.log_level
    if config.cwd is not None:
        overrides["cwd"] = config.cwd  # consumed by the subprocess layer, not RuntimeOptions
    if config.python_executable is not None:
        overrides["python_executable"] = config.python_executable

    # Browser + dashboard mode.
    overrides["browser"] = config.browser
    if config.no_dashboard:
        overrides["no_dashboard"] = True
    if config.no_instrumentation:
        overrides["no_instrumentation"] = True

    # Recording — populated only when the user actually asked for it.
    if config.recording.enabled and config.recording.output_path is not None:
        overrides["recording_output"] = str(config.recording.output_path)

    return overrides
