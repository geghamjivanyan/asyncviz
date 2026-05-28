"""Typed CLI configuration value objects.

The parser produces a :class:`RunCliConfig`; commands + the launcher
consume that frozen dataclass without re-reading argparse.Namespace
attributes. Pulling the configuration into a type makes the runtime
launcher trivially testable — feed it a config + assert side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from asyncviz.cli.configuration.defaults import (
    DEFAULT_BROWSER_PREFERENCE,
    DEFAULT_DASHBOARD_HOST,
    DEFAULT_DASHBOARD_PORT,
    DEFAULT_STARTUP_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_SHUTDOWN_TIMEOUT_SECONDS,
)

BrowserPreference = Literal["auto", "always", "never"]
"""Tri-state preference for browser auto-open."""

TargetKind = Literal["script", "module"]


@dataclass(frozen=True, slots=True)
class TargetSpec:
    """What the user wants AsyncViz to run.

    * ``kind="script"`` + ``value`` is the path to a ``.py`` file.
    * ``kind="module"`` + ``value`` is the dotted module name (``runpy``-style).
    * ``argv`` is the argv vector the target sees as ``sys.argv``.
      ``argv[0]`` matches what Python would normally set:
      script path for scripts, the module name for ``-m`` modules.
    """

    kind: TargetKind
    value: str
    argv: tuple[str, ...] = field(default_factory=tuple)

    def display_name(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RecordingOptions:
    """Replay-recording configuration injected from ``asyncviz record``.

    Kept as its own dataclass so the ``run`` command stays
    record-unaware — only the ``record`` command populates this. The
    fields mirror :class:`asyncviz.runtime.replay.recorder.RecorderConfig`
    so the bootstrap entry can hydrate it without an adapter layer.
    """

    enabled: bool = False
    output_path: Path | None = None
    compression: str = "gzip"
    chunk_events: int = 4096
    chunk_bytes: int = 4 * 1024 * 1024
    queue_capacity: int = 16_384
    flush_interval_seconds: float = 1.0
    include_event_types: tuple[str, ...] | None = None
    exclude_event_types: tuple[str, ...] = field(default_factory=tuple)
    metadata_overrides: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    capture_runtime_snapshot: bool = True
    capture_warning_snapshot: bool = True
    backpressure: str = "drop_newest"


@dataclass(frozen=True, slots=True)
class ReplayCliConfig:
    """Resolved configuration for ``asyncviz replay``.

    Mirrors the user-facing CLI surface for the replay subcommand:
    open the supplied ``.avz`` bundle, spin up the dashboard pointing
    at it, and run the playback engine. The dashboard runs in
    "no live workload" mode — instrumentation is left disabled, the
    lag monitor is left idle, and the only frames websocket clients
    see are the ones the replay engine emits.

    Kept distinct from :class:`RunCliConfig` because the two flows
    don't share most knobs: replay has no target script, no
    instrumentation toggle, no recording surface, no env overrides,
    no cwd. Conflating them would force every ``RunCliConfig``
    consumer to ignore a growing tail of mode-specific fields.
    """

    bundle_path: Path
    """Filesystem path to the ``.avz`` recording bundle directory."""
    host: str = DEFAULT_DASHBOARD_HOST
    port: int = DEFAULT_DASHBOARD_PORT
    browser: BrowserPreference = DEFAULT_BROWSER_PREFERENCE
    startup_timeout: float = DEFAULT_STARTUP_TIMEOUT_SECONDS
    speed: float = 1.0
    """Initial playback speed multiplier. 1.0 = real-time cadence."""
    autoplay: bool = True
    """When ``False``, hydrate the dashboard but leave the engine
    paused so the operator can drive playback from the UI."""
    verify_integrity: bool = True
    """Run the bundle's integrity verifier before replay starts."""
    rebuild_manifest_if_missing: bool = False
    """Attempt to rebuild ``manifest.json`` from a chunk scan when
    it's absent. Useful for partially-finalized recordings; disabled
    by default because a missing manifest usually points at a
    corrupted bundle and the operator should opt in explicitly."""
    debug: bool = False
    log_level: str | None = None
    quiet: bool = False

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass(frozen=True, slots=True)
class RunCliConfig:
    """Resolved configuration for ``asyncviz run``.

    Fields mirror the CLI surface 1:1. Defaults are baked in so commands
    that build a config programmatically (tests, plugins) don't have to
    repeat the parser's defaulting logic.
    """

    target: TargetSpec
    host: str = DEFAULT_DASHBOARD_HOST
    port: int = DEFAULT_DASHBOARD_PORT
    browser: BrowserPreference = DEFAULT_BROWSER_PREFERENCE
    startup_timeout: float = DEFAULT_STARTUP_TIMEOUT_SECONDS
    shutdown_timeout: float = DEFAULT_SUBPROCESS_SHUTDOWN_TIMEOUT_SECONDS
    python_executable: str | None = None
    """Override the interpreter used to run the target subprocess."""
    debug: bool = False
    """Forward to ``asyncviz.start(debug=True)``."""
    enable_instrumentation: bool = True
    """When False, the dashboard starts but asyncio instrumentation does not."""
    log_level: str | None = None
    cwd: Path | None = None
    """Working directory for the target subprocess. None = inherit."""
    env_overrides: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    """Extra env vars to set on the subprocess (``-e KEY=VAL`` flag)."""
    quiet: bool = False
    """Suppress the AsyncViz banner."""
    no_dashboard: bool = False
    """Run instrumentation only — don't start the embedded dashboard.
    Useful for record-only modes / future replay capture flows."""
    recording: RecordingOptions = field(default_factory=RecordingOptions)
    """Replay-recording configuration. Empty by default; the
    ``record`` command populates it."""

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.host}:{self.port}"
