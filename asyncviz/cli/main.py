"""Process entry point for the ``asyncviz`` console script.

Kept tiny so ``python -m asyncviz`` and the wheel-installed
``asyncviz`` command both share one canonical wrapper.
"""

from __future__ import annotations

import sys

from asyncviz.cli.entrypoint import run_cli


def main(argv: list[str] | None = None) -> int:
    """Run the CLI; return the exit code (does not call ``sys.exit``)."""
    return run_cli(argv)


def cli() -> None:
    """Console-script entrypoint that calls ``sys.exit``."""
    sys.exit(main())
