"""Provenance tracking for resolved configuration values.

Every option in the canonical :class:`RuntimeOptions` carries a
sibling :class:`OptionSource` so the diagnostics endpoint + the
``asyncviz doctor`` command can answer "where did this value come
from?" without re-running the resolver.

The enum is ordered by precedence (lower = weaker). A merge picks
the higher source's value when both are present.
"""

from __future__ import annotations

from enum import IntEnum


class OptionSource(IntEnum):
    """Where a resolved option came from. Higher value = wins on merge."""

    UNSET = 0
    """Option still carries its default — no source has spoken for it."""

    DEFAULT = 10
    """Hard-coded default from :mod:`runtime_defaults`."""

    PROFILE = 20
    """Named profile (dev/prod/ci) supplied a value."""

    CONFIG_FILE = 30
    """Reserved — future TOML/YAML config file source."""

    ENVIRONMENT = 40
    """Environment variable supplied a value."""

    API_KWARGS = 50
    """:func:`asyncviz.start` keyword argument."""

    CLI = 60
    """Explicit ``--flag`` on the command line."""

    OVERRIDE = 70
    """Programmatic override (tests / late-binding adapters)."""

    def precedes(self, other: OptionSource) -> bool:
        """Return True when ``self`` should win over ``other`` on a merge."""
        return int(self) >= int(other)
