"""Validation rules for :class:`RunCliConfig`.

Split from the parser so the same checks apply whether the config
comes from argparse, a plugin, or a Python API call. Every failure
raises :class:`ConfigurationValidationError` with a user-friendly
message — the calling command translates that to an exit code.
"""

from __future__ import annotations

import re
from pathlib import Path

from asyncviz.cli.configuration.cli_configuration import (
    RunCliConfig,
    TargetSpec,
)

_HOST_RE = re.compile(r"^[a-zA-Z0-9_\-.:%]+$")
_MODULE_RE = re.compile(r"^[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*$")


class ConfigurationValidationError(ValueError):
    """Raised when a CLI config fails validation."""


def _validate_host(host: str) -> None:
    if not host or not _HOST_RE.match(host):
        raise ConfigurationValidationError(
            f"invalid host {host!r}: must contain only letters, digits, "
            "dot, dash, colon, or underscore",
        )


def _validate_port(port: int) -> None:
    if not (1 <= port <= 65535):
        raise ConfigurationValidationError(
            f"invalid port {port!r}: must be in the range 1..65535",
        )


def _validate_timeout(label: str, value: float) -> None:
    if value < 0:
        raise ConfigurationValidationError(
            f"invalid {label} timeout {value!r}: must be non-negative",
        )


def _validate_target(target: TargetSpec) -> None:
    if target.kind == "script":
        path = Path(target.value)
        if not path.is_file():
            raise ConfigurationValidationError(
                f"script not found: {target.value}",
            )
        if path.suffix not in (".py", ".pyw"):
            # Don't hard-fail on extension; warn callers via a softer
            # validator hook in the future. For now, just accept it —
            # ``runpy.run_path`` will handle the actual loading.
            pass
    elif target.kind == "module":
        if not _MODULE_RE.match(target.value):
            raise ConfigurationValidationError(
                f"invalid module name {target.value!r}: "
                f"must be a dotted Python identifier (e.g. 'pkg.module')",
            )
    else:  # pragma: no cover — exhaustiveness guard
        raise ConfigurationValidationError(
            f"unsupported target kind {target.kind!r}",
        )


def _validate_python_executable(python: str | None) -> None:
    if python is None:
        return
    if not python.strip():
        raise ConfigurationValidationError("--python must not be empty")


def _validate_cwd(cwd: Path | None) -> None:
    if cwd is None:
        return
    if not cwd.is_dir():
        raise ConfigurationValidationError(f"cwd does not exist: {cwd}")


def _validate_env_overrides(overrides: tuple[tuple[str, str], ...]) -> None:
    for name, _ in overrides:
        if not name or "=" in name:
            raise ConfigurationValidationError(
                f"invalid env var name {name!r}: must be non-empty and contain no '='",
            )


def validate_run_config(config: RunCliConfig) -> None:
    """Run every check against ``config``; raises on the first failure."""
    _validate_host(config.host)
    _validate_port(config.port)
    _validate_timeout("startup", config.startup_timeout)
    _validate_timeout("shutdown", config.shutdown_timeout)
    _validate_python_executable(config.python_executable)
    _validate_cwd(config.cwd)
    _validate_env_overrides(config.env_overrides)
    _validate_target(config.target)
