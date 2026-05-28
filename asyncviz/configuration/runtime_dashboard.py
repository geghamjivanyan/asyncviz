"""Dashboard-related runtime options.

Mirrors the fields :class:`asyncviz.AsyncVizConfig` carries today but
split into a focused dataclass so future per-domain overrides
(``--dashboard-*`` flags, profile-driven defaults) plug in without
ballooning the top-level options struct.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from asyncviz.configuration.runtime_defaults import (
    DEFAULT_DEBUG,
    DEFAULT_FRONTEND_MODE,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_LOG_LEVEL,
    DEFAULT_STARTUP_TIMEOUT_SECONDS,
)

FrontendMode = Literal["auto", "embedded", "api-only"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass(frozen=True, slots=True)
class DashboardOptions:
    """Configuration for the embedded FastAPI dashboard."""

    debug: bool = DEFAULT_DEBUG
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    startup_timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS
    log_level: LogLevel | None = DEFAULT_LOG_LEVEL
    frontend_mode: FrontendMode = DEFAULT_FRONTEND_MODE

    @property
    def effective_log_level(self) -> LogLevel:
        if self.log_level is not None:
            return self.log_level
        return "DEBUG" if self.debug else "INFO"
