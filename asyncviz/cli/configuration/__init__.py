"""Typed CLI configuration surface.

Splits the configuration vocabulary from the parser so commands can
read typed values without re-doing argparse semantics. Defaults live
next to the type so changes flow through one place.
"""

from asyncviz.cli.configuration.cli_configuration import (
    BrowserPreference,
    RecordingOptions,
    ReplayCliConfig,
    RunCliConfig,
    TargetSpec,
)
from asyncviz.cli.configuration.defaults import (
    DEFAULT_BROWSER_PREFERENCE,
    DEFAULT_DASHBOARD_HOST,
    DEFAULT_DASHBOARD_PORT,
    DEFAULT_STARTUP_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_SHUTDOWN_TIMEOUT_SECONDS,
)
from asyncviz.cli.configuration.validation import (
    ConfigurationValidationError,
    validate_run_config,
)

__all__ = [
    "DEFAULT_BROWSER_PREFERENCE",
    "DEFAULT_DASHBOARD_HOST",
    "DEFAULT_DASHBOARD_PORT",
    "DEFAULT_STARTUP_TIMEOUT_SECONDS",
    "DEFAULT_SUBPROCESS_SHUTDOWN_TIMEOUT_SECONDS",
    "BrowserPreference",
    "ConfigurationValidationError",
    "RecordingOptions",
    "ReplayCliConfig",
    "RunCliConfig",
    "TargetSpec",
    "validate_run_config",
]
