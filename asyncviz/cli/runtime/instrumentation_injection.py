"""Construct the subprocess command line.

Today this is a one-liner: ``python -m asyncviz.cli.runtime.bootstrap_entry``.
The module exists as its own layer so the command surface is the only
place that knows about the bootstrap entry path — if we later switch
to ``-X`` injection or to a sitecustomize approach for "attach to an
already-running process", call sites stay stable.
"""

from __future__ import annotations

import sys
from pathlib import Path

from asyncviz.cli.configuration import RunCliConfig

#: Module the subprocess executes via ``python -m``. Importing it
#: here would be cheaper at startup but the import would pull
#: ``asyncviz`` into the parent CLI process, which is fine but
#: unnecessary — we just need the dotted name.
BOOTSTRAP_MODULE = "asyncviz.cli.runtime.bootstrap_entry"


def build_bootstrap_command(config: RunCliConfig) -> list[str]:
    """Return ``argv`` for the subprocess that runs the AsyncViz bootstrap."""
    python = _resolve_python(config.python_executable)
    return [python, "-m", BOOTSTRAP_MODULE]


def _resolve_python(override: str | None) -> str:
    """Resolve the interpreter to use, preserving the parent's by default."""
    if override is None:
        return sys.executable
    # If the user passed an absolute path, accept it as-is. Otherwise
    # leave the lookup to the OS (``subprocess`` resolves via PATH).
    candidate = Path(override)
    if candidate.is_absolute():
        return str(candidate)
    return override
