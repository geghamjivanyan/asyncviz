"""CLI subcommand implementations.

Each module here owns one verb (``run``, ``doctor``, ``version``).
The dispatcher in :mod:`asyncviz.cli.entrypoint` picks the right
callable based on the parsed command.
"""

from asyncviz.cli.commands.doctor import run as doctor_command
from asyncviz.cli.commands.record import run as record_command
from asyncviz.cli.commands.replay import run as replay_command
from asyncviz.cli.commands.run import run as run_command
from asyncviz.cli.commands.version import run as version_command

__all__ = [
    "doctor_command",
    "record_command",
    "replay_command",
    "run_command",
    "version_command",
]
