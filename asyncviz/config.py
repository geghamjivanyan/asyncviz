from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Self, get_args

from asyncviz.utils.env import parse_bool, parse_float, parse_int

ENV_PREFIX = "ASYNCVIZ_"

FrontendMode = Literal["auto", "embedded", "api-only"]
FRONTEND_MODES: tuple[FrontendMode, ...] = get_args(FrontendMode)

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LOG_LEVELS: tuple[LogLevel, ...] = get_args(LogLevel)

#: Built-in CORS allow-list. Tuned for the Vite standalone dev mode
#: documented in ``frontend/src/app/configuration/runtimeConfig.ts``:
#: the frontend runs on ``:5173`` (host or loopback) and calls back to
#: the backend's :class:`AsyncVizConfig.port`. These origins are safe
#: to leave on in production — they only opt those two specific
#: development origins into the ``Access-Control-Allow-Origin`` echo,
#: and a malicious page on those origins would already need code
#: execution on the operator's machine to matter.
DEFAULT_CORS_ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


@dataclass(frozen=True, slots=True)
class AsyncVizConfig:
    host: str = "127.0.0.1"
    port: int = 8877
    open_browser: bool = True
    debug: bool = False
    heartbeat_interval: float = 5.0
    frontend_mode: FrontendMode = "auto"
    log_level: LogLevel | None = None
    startup_timeout: float = 5.0
    enable_instrumentation: bool = True
    #: Explicit CORS allow-list — :class:`CORSMiddleware` echoes
    #: ``Access-Control-Allow-Origin`` only for these origins.
    #:
    #:   * An empty tuple disables the CORS middleware entirely
    #:     (same-origin deployments don't need it).
    #:   * The single-element ``("*",)`` is interpreted as "wildcard"
    #:     and forces ``allow_credentials=False`` (the browser would
    #:     reject credentialed requests against ``*`` anyway).
    #:   * Otherwise, the listed origins are echoed verbatim with
    #:     ``allow_credentials=True``.
    cors_allowed_origins: tuple[str, ...] = DEFAULT_CORS_ALLOWED_ORIGINS

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def effective_log_level(self) -> LogLevel:
        if self.log_level is not None:
            return self.log_level
        return "DEBUG" if self.debug else "INFO"

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Self:
        env = environ if environ is not None else os.environ
        defaults = cls()
        return cls(
            host=env.get(f"{ENV_PREFIX}HOST", defaults.host),
            port=parse_int(env.get(f"{ENV_PREFIX}PORT"), defaults.port),
            open_browser=parse_bool(env.get(f"{ENV_PREFIX}OPEN_BROWSER"), defaults.open_browser),
            debug=parse_bool(env.get(f"{ENV_PREFIX}DEBUG"), defaults.debug),
            heartbeat_interval=parse_float(
                env.get(f"{ENV_PREFIX}HEARTBEAT_INTERVAL"), defaults.heartbeat_interval
            ),
            frontend_mode=_parse_frontend_mode(
                env.get(f"{ENV_PREFIX}FRONTEND_MODE"), defaults.frontend_mode
            ),
            log_level=_parse_log_level(env.get(f"{ENV_PREFIX}LOG_LEVEL"), defaults.log_level),
            startup_timeout=parse_float(
                env.get(f"{ENV_PREFIX}STARTUP_TIMEOUT"), defaults.startup_timeout
            ),
            enable_instrumentation=parse_bool(
                env.get(f"{ENV_PREFIX}ENABLE_INSTRUMENTATION"),
                defaults.enable_instrumentation,
            ),
            cors_allowed_origins=_parse_cors_allowed_origins(
                env.get(f"{ENV_PREFIX}CORS_ALLOWED_ORIGINS"),
                defaults.cors_allowed_origins,
            ),
        )


def _parse_frontend_mode(value: str | None, default: FrontendMode) -> FrontendMode:
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized not in FRONTEND_MODES:
        raise ValueError(f"frontend_mode must be one of {FRONTEND_MODES}, got {value!r}")
    return normalized  # type: ignore[return-value]


def _parse_log_level(value: str | None, default: LogLevel | None) -> LogLevel | None:
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().upper()
    if normalized not in LOG_LEVELS:
        raise ValueError(f"log_level must be one of {LOG_LEVELS}, got {value!r}")
    return normalized  # type: ignore[return-value]


def _parse_cors_allowed_origins(
    value: str | None,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    """Parse the ``ASYNCVIZ_CORS_ALLOWED_ORIGINS`` env var.

    Accepts a comma-separated list of origins. Empty whitespace
    between commas is dropped silently. The special token
    ``"none"`` (case-insensitive, as the entire value) is parsed
    as the empty tuple — i.e. "disable CORS entirely".

    ``None`` and the empty string both fall through to the default,
    matching how every other env helper in this module behaves.
    """
    if value is None:
        return default
    stripped = value.strip()
    if stripped == "":
        return default
    if stripped.lower() == "none":
        return ()
    parts = tuple(token.strip() for token in stripped.split(",") if token.strip())
    return parts if parts else default

