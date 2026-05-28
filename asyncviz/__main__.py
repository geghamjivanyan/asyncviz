"""``python -m asyncviz`` entry point.

Delegates to the canonical CLI dispatcher in :mod:`asyncviz.cli`.
Kept tiny so a future plugin system can replace ``run_cli`` without
touching the module path users invoke from the shell.
"""

from __future__ import annotations

import sys

from asyncviz.cli import run_cli


def main() -> int:
    """Process entry point — returns the exit code without calling sys.exit."""
    return run_cli()


if __name__ == "__main__":
    sys.exit(main())
