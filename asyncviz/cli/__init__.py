"""Canonical CLI surface for AsyncViz.

The public exports are deliberately small — ``main`` keeps backwards
compatibility with the legacy ``asyncviz.cli.main`` import, while the
new ``run_cli`` exposes the dispatcher so plugins (and tests) can
drive it without going through ``sys.argv``.
"""

from asyncviz.cli.entrypoint import run_cli
from asyncviz.cli.main import cli, main

__all__ = ["cli", "main", "run_cli"]
