from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

from asyncviz.config import AsyncVizConfig, FrontendMode, LogLevel


def resolve_config(
    *,
    host: str | None = None,
    port: int | None = None,
    open_browser: bool | None = None,
    debug: bool | None = None,
    heartbeat_interval: float | None = None,
    frontend_mode: FrontendMode | None = None,
    log_level: LogLevel | None = None,
    startup_timeout: float | None = None,
    enable_instrumentation: bool | None = None,
    cors_allowed_origins: Iterable[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> AsyncVizConfig:
    """Build an :class:`AsyncVizConfig` with the documented precedence rules.

    Precedence (highest first):
      1. Explicit function arguments (non-``None`` values).
      2. Environment variables (``ASYNCVIZ_*``).
      3. Built-in defaults declared on :class:`AsyncVizConfig`.
    """
    base = AsyncVizConfig.from_env(dict(env) if env is not None else None)

    overrides: dict[str, object] = {}
    if host is not None:
        overrides["host"] = host
    if port is not None:
        overrides["port"] = port
    if open_browser is not None:
        overrides["open_browser"] = open_browser
    if debug is not None:
        overrides["debug"] = debug
    if heartbeat_interval is not None:
        overrides["heartbeat_interval"] = heartbeat_interval
    if frontend_mode is not None:
        overrides["frontend_mode"] = frontend_mode
    if log_level is not None:
        overrides["log_level"] = log_level
    if startup_timeout is not None:
        overrides["startup_timeout"] = startup_timeout
    if enable_instrumentation is not None:
        overrides["enable_instrumentation"] = enable_instrumentation
    if cors_allowed_origins is not None:
        overrides["cors_allowed_origins"] = tuple(cors_allowed_origins)

    return replace(base, **overrides)  # type: ignore[arg-type]
