"""Top-level CLI dispatcher.

Splits "parse argv" from "run the command" so the parser stays
testable in isolation + every command shares the same error-handling
chrome (logging, exit codes, diagnostics).
"""

from __future__ import annotations

import time

from asyncviz.cli.commands import (
    doctor_command,
    record_command,
    replay_command,
    run_command,
    version_command,
)
from asyncviz.cli.exit_codes import ExitCode
from asyncviz.cli.output import error
from asyncviz.cli.parser import parse
from asyncviz.cli.runtime.diagnostics import record_lifecycle_event
from asyncviz.cli.runtime.observability import get_cli_metrics
from asyncviz.utils.env import load_dotenv


def run_cli(argv: list[str] | None = None) -> int:
    """Resolve + dispatch one CLI invocation.

    Returns the exit code the OS should see — :func:`main` wraps this
    in a ``sys.exit`` call.
    """
    load_dotenv()

    record_lifecycle_event("parse-start", "")
    parse_started = time.monotonic()
    try:
        parsed, args = parse(argv)
    except SystemExit as exc:
        # Argparse already wrote help/usage to stderr.
        record_lifecycle_event("parse-failure", str(exc.code))
        code = exc.code
        if isinstance(code, int):
            return code
        return int(ExitCode.USAGE_ERROR)
    finally:
        elapsed_ms = (time.monotonic() - parse_started) * 1000
        get_cli_metrics().record_parse_duration(elapsed_ms)

    record_lifecycle_event("parse-success", parsed.command)

    try:
        if parsed.command == "run":
            return run_command(args, config=parsed.run_config)
        if parsed.command == "record":
            return record_command(args, config=parsed.run_config)
        if parsed.command == "replay":
            return replay_command(args, config=parsed.replay_config)
        if parsed.command == "doctor":
            return doctor_command(args)
        if parsed.command == "version":
            return version_command(args)
        error(f"unknown command: {parsed.command!r}")
        return int(ExitCode.USAGE_ERROR)
    except KeyboardInterrupt:
        return int(ExitCode.INTERRUPTED)
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return int(ExitCode.GENERIC_FAILURE)
    except Exception as exc:  # pragma: no cover — defensive
        error(f"unhandled error: {exc}")
        return int(ExitCode.GENERIC_FAILURE)
