"""Per-subsystem integration scenarios.

Importing this package registers every built-in scenario with the
default :class:`IntegrationRegistry`. Tests that want a clean
registry call :func:`reset_default_registry` first.
"""

from tests.integration.scenarios._builtins import (
    register_builtin_scenarios,
    reset_builtin_flag,
)

__all__ = ["register_builtin_scenarios", "reset_builtin_flag"]
