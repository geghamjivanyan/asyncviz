from __future__ import annotations

import socket
from contextlib import closing
from pathlib import Path

from asyncviz.config import FRONTEND_MODES, LOG_LEVELS, AsyncVizConfig


class AsyncVizError(Exception):
    """Base class for every AsyncViz-raised bootstrap error."""


class ConfigError(AsyncVizError):
    """Raised when an :class:`AsyncVizConfig` is invalid."""


class StartupError(AsyncVizError):
    """Raised when bringing the runtime up fails."""


class StartupTimeoutError(StartupError):
    """Raised when uvicorn doesn't signal readiness within the configured window."""


class PortInUseError(StartupError):
    """Raised when the requested host/port is already bound."""


def validate_config(config: AsyncVizConfig) -> None:
    if not isinstance(config.host, str) or not config.host.strip():
        raise ConfigError("host must be a non-empty string")
    if not (1 <= config.port <= 65535):
        raise ConfigError(f"port must be in 1..65535 (got {config.port})")
    if config.heartbeat_interval <= 0:
        raise ConfigError(f"heartbeat_interval must be > 0 (got {config.heartbeat_interval})")
    if config.startup_timeout <= 0:
        raise ConfigError(f"startup_timeout must be > 0 (got {config.startup_timeout})")
    if config.frontend_mode not in FRONTEND_MODES:
        raise ConfigError(
            f"frontend_mode must be one of {FRONTEND_MODES} (got {config.frontend_mode!r})"
        )
    if config.log_level is not None and config.log_level not in LOG_LEVELS:
        raise ConfigError(f"log_level must be one of {LOG_LEVELS} (got {config.log_level!r})")


def check_frontend_mode(config: AsyncVizConfig, static_dir: Path) -> None:
    """Validate frontend_mode against the embedded bundle's presence."""
    has_bundle = (static_dir / "index.html").is_file()
    if config.frontend_mode == "embedded" and not has_bundle:
        raise ConfigError(
            f"frontend_mode='embedded' requires a built SPA at {static_dir}; "
            "run `make embed-frontend` first."
        )


def check_port_available(host: str, port: int) -> None:
    """Pre-flight check — raise :class:`PortInUseError` if the bind would fail.

    There is an inherent TOCTOU race between this check and uvicorn's bind,
    but the upside is a clean error message before any threads are spawned.
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            sock.bind((host, port))
        except OSError as exc:
            raise PortInUseError(f"port {port} on {host} is already in use") from exc
