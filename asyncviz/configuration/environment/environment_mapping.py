"""Declarative env-var → option-path registry.

Every ``ASYNCVIZ_*`` variable the core loader honours lives here as
an :class:`EnvVarSpec`. Adding a new option is a one-line append +
the loader picks it up automatically. The registry is the source of
truth for diagnostics ("which env vars do I know about?") + the
``--help`` output for the future ``asyncviz env`` subcommand.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from asyncviz.configuration.environment.environment_defaults import DEFAULT_NAMESPACE
from asyncviz.configuration.environment.environment_parser import (
    PARSER_REGISTRY,
    Parser,
    parse_enum,
    parse_list,
)
from asyncviz.configuration.environment.environment_types import ParseKind


@dataclass(frozen=True, slots=True)
class EnvVarSpec:
    """One env var the loader knows about.

    The ``target`` path is dotted (``network.port``,
    ``recording.enabled``) and matches the canonical
    :class:`RuntimeOptions` shape. The loader uses it both to apply
    the value + to record provenance.
    """

    env_name: str
    target: str
    kind: ParseKind
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    """Additional env-var names that map to the same option.
    Resolved with priority (first alias wins among aliases)."""
    choices: tuple[str, ...] = field(default_factory=tuple)
    """Populated for ``ParseKind.ENUM`` entries."""
    list_separator: str = ","
    """Populated for ``ParseKind.LIST`` entries."""
    secret: bool = False
    """When True, the value is redacted from diagnostics."""

    def all_names(self) -> tuple[str, ...]:
        return (self.env_name, *self.aliases)

    def build_parser(self) -> Parser:
        if self.kind is ParseKind.ENUM:
            return parse_enum(choices=self.choices)
        if self.kind is ParseKind.LIST:
            return parse_list(separator=self.list_separator)
        try:
            return PARSER_REGISTRY[self.kind]
        except KeyError as exc:  # pragma: no cover — defensive
            raise RuntimeError(f"no parser registered for {self.kind!r}") from exc


def _spec(name: str, target: str, kind: ParseKind, **kwargs: object) -> EnvVarSpec:
    return EnvVarSpec(env_name=f"{DEFAULT_NAMESPACE}{name}", target=target, kind=kind, **kwargs)


#: Canonical core mapping. Order matters only for diagnostics rendering.
CORE_ENV_VAR_SPECS: tuple[EnvVarSpec, ...] = (
    # ── network ──
    _spec("HOST", "network.host", ParseKind.STRING, description="Dashboard bind host."),
    _spec("PORT", "network.port", ParseKind.INT, description="Dashboard bind port."),
    # ── dashboard ──
    _spec(
        "DEBUG",
        "dashboard.debug",
        ParseKind.BOOL,
        description="Enable verbose backend logging.",
    ),
    _spec(
        "LOG_LEVEL",
        "dashboard.log_level",
        ParseKind.ENUM,
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        description="Backend log level.",
    ),
    _spec(
        "FRONTEND_MODE",
        "dashboard.frontend_mode",
        ParseKind.ENUM,
        choices=("auto", "embedded", "api-only"),
        description="Frontend bundle resolution policy.",
    ),
    _spec(
        "HEARTBEAT_INTERVAL",
        "dashboard.heartbeat_interval_seconds",
        ParseKind.DURATION_SECONDS,
        description="Server-sent heartbeat cadence (seconds; supports '5s'/'500ms').",
    ),
    _spec(
        "STARTUP_TIMEOUT",
        "dashboard.startup_timeout_seconds",
        ParseKind.DURATION_SECONDS,
        description="Max wait for the embedded uvicorn server to become ready.",
    ),
    # ── browser ──
    _spec(
        "BROWSER",
        "browser.policy",
        ParseKind.ENUM,
        choices=("auto", "always", "never"),
        description="Browser auto-open policy.",
    ),
    _spec(
        "NO_BROWSER",
        "browser.policy",
        ParseKind.BOOL,
        description="When truthy, force ``browser.policy=never`` (hard-off).",
    ),
    # ── monitoring ──
    _spec(
        "ENABLE_INSTRUMENTATION",
        "monitoring.enable_instrumentation",
        ParseKind.BOOL,
        description="Toggle the asyncio patcher.",
    ),
    _spec(
        "LAG_WARNING_MS",
        "monitoring.lag_warning_ms",
        ParseKind.DURATION_MS,
        description="Warning-tier event-loop lag threshold (e.g. '50ms').",
    ),
    _spec(
        "LAG_CRITICAL_MS",
        "monitoring.lag_critical_ms",
        ParseKind.DURATION_MS,
        description="Critical-tier event-loop lag threshold.",
    ),
    _spec(
        "LAG_FREEZE_MS",
        "monitoring.lag_freeze_ms",
        ParseKind.DURATION_MS,
        description="Freeze-tier event-loop lag threshold.",
    ),
    _spec(
        "LAG_SAMPLE_INTERVAL_MS",
        "monitoring.lag_sample_interval_ms",
        ParseKind.DURATION_MS,
        description="Sampling interval for the lag monitor.",
    ),
    _spec(
        "CAPTURE_STACK_TRACES",
        "monitoring.capture_stack_traces",
        ParseKind.BOOL,
        description="Toggle stack-capture during freezes.",
    ),
    # ── recording ──
    _spec(
        "RECORDING_OUTPUT",
        "recording.output_path",
        ParseKind.PATH,
        description="Path to write the replay bundle. Setting this also enables recording.",
    ),
    _spec(
        "RECORDING_COMPRESSION",
        "recording.compression",
        ParseKind.ENUM,
        choices=("none", "gzip"),
        description="Per-chunk compression for the replay recorder.",
    ),
    _spec(
        "RECORDING_CHUNK_EVENTS",
        "recording.chunk_events",
        ParseKind.INT,
        description="Roll a chunk after this many events.",
    ),
    _spec(
        "RECORDING_CHUNK_BYTES",
        "recording.chunk_bytes",
        ParseKind.INT,
        description="Roll a chunk after this many bytes.",
    ),
    _spec(
        "RECORDING_QUEUE_CAPACITY",
        "recording.queue_capacity",
        ParseKind.INT,
        description="In-memory backpressure queue depth.",
    ),
    _spec(
        "RECORDING_BACKPRESSURE",
        "recording.backpressure",
        ParseKind.ENUM,
        choices=("drop_newest", "drop_oldest"),
        description="Backpressure mode when the recorder queue fills.",
    ),
    _spec(
        "RECORDING_INCLUDE_EVENTS",
        "recording.include_event_types",
        ParseKind.LIST,
        description="Comma-separated event types to record (default: all).",
    ),
    _spec(
        "RECORDING_EXCLUDE_EVENTS",
        "recording.exclude_event_types",
        ParseKind.LIST,
        description="Comma-separated event types to skip.",
    ),
    # ── replay ──
    _spec(
        "REPLAY_BUFFER_CAPACITY",
        "replay.buffer_capacity",
        ParseKind.INT,
        description="In-memory replay buffer event capacity.",
    ),
    _spec(
        "REPLAY_RETENTION",
        "replay.retention_seconds",
        ParseKind.DURATION_SECONDS,
        description="In-memory replay retention window.",
    ),
    # ── security ──
    _spec(
        "BIND_LOOPBACK_ONLY",
        "security.bind_loopback_only",
        ParseKind.BOOL,
        description="Reject non-loopback binds when True.",
    ),
    _spec(
        "ALLOW_REMOTE",
        "security.allow_remote_connections",
        ParseKind.BOOL,
        description="Opt-in to non-loopback dashboard binds.",
    ),
)


def core_specs() -> tuple[EnvVarSpec, ...]:
    return CORE_ENV_VAR_SPECS


def specs_by_env_name() -> dict[str, EnvVarSpec]:
    """Flat lookup keyed by every alias + canonical name."""
    out: dict[str, EnvVarSpec] = {}
    for spec in CORE_ENV_VAR_SPECS:
        for name in spec.all_names():
            out[name] = spec
    return out


def known_env_names(specs: Sequence[EnvVarSpec] = CORE_ENV_VAR_SPECS) -> tuple[str, ...]:
    """Every env-var name the loader will react to (canonical first)."""
    names: list[str] = []
    for spec in specs:
        names.append(spec.env_name)
        names.extend(spec.aliases)
    return tuple(names)
