"""Argument parser for the canonical ``asyncviz`` CLI.

argparse is fine for the size of the surface today (run / doctor /
version) — we deliberately avoid Click/Typer so the wheel doesn't
gain extra runtime deps. The parser is structured so each subcommand
gets its own builder + Namespace→typed-config converter; commands
never read raw Namespaces.

The parsing layer is *pure*: it just converts ``argv`` into a
:class:`ParsedCommand`. Side effects (launching, signal handling)
happen in :mod:`asyncviz.cli.commands`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from asyncviz.cli.configuration import (
    DEFAULT_BROWSER_PREFERENCE,
    DEFAULT_DASHBOARD_HOST,
    DEFAULT_DASHBOARD_PORT,
    DEFAULT_STARTUP_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_SHUTDOWN_TIMEOUT_SECONDS,
    RecordingOptions,
    ReplayCliConfig,
    RunCliConfig,
    TargetSpec,
)
from asyncviz.packaging import package_version

CommandName = Literal["run", "record", "replay", "doctor", "version"]

PROGRAM_NAME = "asyncviz"


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    """Result of parsing the global argv vector."""

    command: CommandName
    run_config: RunCliConfig | None = None
    """Populated when ``command in ("run", "record")``."""
    replay_config: ReplayCliConfig | None = None
    """Populated when ``command == "replay"``."""


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser + register every subcommand."""
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        description="AsyncViz — realtime runtime diagnostics for Python asyncio.",
        epilog=(
            "Run 'asyncviz <command> --help' for command-specific help.\n"
            "Examples:\n"
            "  asyncviz run app.py\n"
            "  asyncviz run -m my.package -- --flag value\n"
            "  asyncviz doctor\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {package_version()}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    _build_run_parser(subparsers)
    _build_record_parser(subparsers)
    _build_replay_parser(subparsers)
    _build_doctor_parser(subparsers)
    _build_version_parser(subparsers)

    return parser


# ── Subcommand builders ────────────────────────────────────────────────


def _build_run_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "run",
        help="Launch a Python script or module with AsyncViz attached.",
        description=(
            "Launch the embedded AsyncViz dashboard + run the requested "
            "Python target in the same process so asyncio instrumentation "
            "can observe it."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # ``-m pkg`` and ``script`` are conceptually mutually exclusive but
    # argparse's mutex groups don't compose with ``REMAINDER`` — we
    # validate the constraint in :func:`_run_namespace_to_config` and
    # raise a SystemExit with a friendly message.
    p.add_argument(
        "-m",
        "--module",
        dest="module",
        help="Import the named module (like `python -m pkg.module`).",
    )
    p.add_argument(
        "script",
        nargs="?",
        help="Path to a Python script (.py) to run.",
    )
    p.add_argument(
        "target_argv",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the target's argv. Use `--` to separate.",
    )

    # Dashboard connection.
    p.add_argument(
        "--host",
        default=DEFAULT_DASHBOARD_HOST,
        help=f"Host the dashboard binds to (default: {DEFAULT_DASHBOARD_HOST}).",
    )
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_DASHBOARD_PORT,
        help=f"Port the dashboard binds to (default: {DEFAULT_DASHBOARD_PORT}).",
    )
    p.add_argument(
        "--browser",
        choices=("auto", "always", "never"),
        default=DEFAULT_BROWSER_PREFERENCE,
        help=f"Open the dashboard in a browser (default: {DEFAULT_BROWSER_PREFERENCE}).",
    )

    # Runtime tuning.
    p.add_argument(
        "--python",
        dest="python_executable",
        help="Use this interpreter for the target subprocess (default: sys.executable).",
    )
    p.add_argument(
        "--startup-timeout",
        type=float,
        default=DEFAULT_STARTUP_TIMEOUT_SECONDS,
        help=(
            "Seconds to wait for the dashboard to be ready "
            f"(default: {DEFAULT_STARTUP_TIMEOUT_SECONDS})."
        ),
    )
    p.add_argument(
        "--shutdown-timeout",
        type=float,
        default=DEFAULT_SUBPROCESS_SHUTDOWN_TIMEOUT_SECONDS,
        help=(
            "Seconds to wait for the target to exit after SIGTERM "
            f"(default: {DEFAULT_SUBPROCESS_SHUTDOWN_TIMEOUT_SECONDS})."
        ),
    )
    p.add_argument(
        "--cwd",
        type=Path,
        help="Working directory for the target subprocess (default: inherit).",
    )
    p.add_argument(
        "-e",
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra environment variable to set on the subprocess. Repeatable.",
    )

    p.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose backend logging.",
    )
    p.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Backend log level. Defaults follow --debug.",
    )
    p.add_argument(
        "--no-instrumentation",
        action="store_true",
        help="Skip asyncio instrumentation patches (dashboard only).",
    )
    p.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Skip starting the embedded dashboard (instrumentation only).",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress the startup banner.",
    )


def _build_record_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "record",
        help="Launch a target like 'run' + capture a replay bundle to disk.",
        description=(
            "Like 'asyncviz run' but additionally records the runtime "
            "event stream into a structured replay bundle (default "
            "extension .avz). The bundle is replay-safe + integrity-checked "
            "+ can be opened later for offline analysis."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # ── Target selection (mirrors run) ──
    p.add_argument(
        "-m",
        "--module",
        dest="module",
        help="Import the named module (like `python -m pkg.module`).",
    )
    p.add_argument(
        "script",
        nargs="?",
        help="Path to a Python script (.py) to run.",
    )
    p.add_argument(
        "target_argv",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to the target's argv. Use `--` to separate.",
    )

    # ── Recording-specific flags ──
    p.add_argument(
        "-o",
        "--output",
        dest="output",
        type=Path,
        help=(
            "Destination bundle directory (default: ./asyncviz-recordings/session-<timestamp>.avz)."
        ),
    )
    p.add_argument(
        "--compress",
        choices=("none", "gzip"),
        default="gzip",
        help="Per-chunk compression mode (default: gzip).",
    )
    p.add_argument(
        "--chunk-events",
        type=int,
        default=4096,
        help="Roll a chunk after this many events (default: 4096).",
    )
    p.add_argument(
        "--chunk-bytes",
        type=int,
        default=4 * 1024 * 1024,
        help="Roll a chunk after this many bytes (default: 4 MiB).",
    )
    p.add_argument(
        "--queue-capacity",
        type=int,
        default=16_384,
        help="In-memory backpressure queue depth (default: 16384).",
    )
    p.add_argument(
        "--flush-interval",
        type=float,
        default=1.0,
        help="Writer flush interval seconds (default: 1.0).",
    )
    p.add_argument(
        "--backpressure",
        choices=("drop_newest", "drop_oldest"),
        default="drop_newest",
        help="How to behave when the recorder queue fills (default: drop_newest).",
    )
    p.add_argument(
        "--include-event",
        action="append",
        default=[],
        metavar="EVENT_TYPE",
        help="Only record events of this type. Repeatable.",
    )
    p.add_argument(
        "--exclude-event",
        action="append",
        default=[],
        metavar="EVENT_TYPE",
        help="Skip events of this type. Repeatable. Wins over --include-event.",
    )
    p.add_argument(
        "--meta",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Free-form metadata key/value pair surfaced in the bundle. Repeatable.",
    )
    p.add_argument(
        "--no-runtime-snapshot",
        action="store_true",
        help="Skip writing the final runtime snapshot.",
    )
    p.add_argument(
        "--no-warning-snapshot",
        action="store_true",
        help="Skip writing the final blocking-warning snapshot.",
    )

    # ── Shared run flags ──
    p.add_argument(
        "--host",
        default=DEFAULT_DASHBOARD_HOST,
        help=f"Host the dashboard binds to (default: {DEFAULT_DASHBOARD_HOST}).",
    )
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_DASHBOARD_PORT,
        help=f"Port the dashboard binds to (default: {DEFAULT_DASHBOARD_PORT}).",
    )
    p.add_argument(
        "--browser",
        choices=("auto", "always", "never"),
        default="never",
        help="Open the dashboard in a browser (default: never for record mode).",
    )
    p.add_argument(
        "--python",
        dest="python_executable",
        help="Use this interpreter for the target subprocess (default: sys.executable).",
    )
    p.add_argument(
        "--startup-timeout",
        type=float,
        default=DEFAULT_STARTUP_TIMEOUT_SECONDS,
        help=f"Dashboard startup timeout (default: {DEFAULT_STARTUP_TIMEOUT_SECONDS}).",
    )
    p.add_argument(
        "--shutdown-timeout",
        type=float,
        default=DEFAULT_SUBPROCESS_SHUTDOWN_TIMEOUT_SECONDS,
        help=f"Target shutdown timeout (default: {DEFAULT_SUBPROCESS_SHUTDOWN_TIMEOUT_SECONDS}).",
    )
    p.add_argument(
        "--cwd",
        type=Path,
        help="Working directory for the target subprocess.",
    )
    p.add_argument(
        "-e",
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra environment variable to set on the subprocess. Repeatable.",
    )
    p.add_argument("--debug", action="store_true", help="Verbose backend logging.")
    p.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Backend log level.",
    )
    p.add_argument(
        "--no-instrumentation",
        action="store_true",
        help="Skip asyncio instrumentation patches.",
    )
    p.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Skip starting the embedded dashboard.",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress the startup banner.")


def _build_replay_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "replay",
        help="Open a recorded replay bundle in the dashboard.",
        description=(
            "Open the dashboard pointing at an existing AsyncViz replay "
            "bundle (.avz directory created by `asyncviz record`). The "
            "live runtime instrumentation stays disabled — the dashboard "
            "renders the recorded session's reconstructed state and "
            "playback controls (play / pause / seek / speed) drive the "
            "replay engine over the bundle's event stream."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  asyncviz replay asyncviz-recordings/session-20260527T044630Z.avz\n"
            "  asyncviz replay path/to/bundle.avz --speed 2.0 --no-autoplay\n"
        ),
    )
    p.add_argument(
        "bundle",
        type=Path,
        help="Path to the .avz recording bundle directory.",
    )
    p.add_argument(
        "--host",
        default=DEFAULT_DASHBOARD_HOST,
        help=f"Host the dashboard binds to (default: {DEFAULT_DASHBOARD_HOST}).",
    )
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_DASHBOARD_PORT,
        help=f"Port the dashboard binds to (default: {DEFAULT_DASHBOARD_PORT}).",
    )
    p.add_argument(
        "--browser",
        choices=("auto", "always", "never"),
        default=DEFAULT_BROWSER_PREFERENCE,
        help=f"Open the dashboard in a browser (default: {DEFAULT_BROWSER_PREFERENCE}).",
    )
    p.add_argument(
        "--startup-timeout",
        type=float,
        default=DEFAULT_STARTUP_TIMEOUT_SECONDS,
        help=(
            "Seconds to wait for the dashboard to be ready "
            f"(default: {DEFAULT_STARTUP_TIMEOUT_SECONDS})."
        ),
    )
    p.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Initial playback speed multiplier (default: 1.0 = real-time).",
    )
    p.add_argument(
        "--no-autoplay",
        dest="autoplay",
        action="store_false",
        default=True,
        help="Hydrate the dashboard but leave the engine paused. The "
        "operator drives playback from the UI.",
    )
    p.add_argument(
        "--no-integrity",
        dest="verify_integrity",
        action="store_false",
        default=True,
        help="Skip the bundle integrity check before replay starts.",
    )
    p.add_argument(
        "--rebuild-manifest",
        dest="rebuild_manifest_if_missing",
        action="store_true",
        default=False,
        help="Rebuild manifest.json from a chunk scan when it's absent. "
        "Useful for partially-finalized recordings.",
    )
    p.add_argument("--debug", action="store_true", help="Verbose backend logging.")
    p.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Backend log level.",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress the startup banner.")


def _build_doctor_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "doctor",
        help="Show packaging + runtime diagnostics for the installed AsyncViz.",
        description=(
            "Print package metadata, frontend bundle state, install shape, and a "
            "summary of CLI environment health checks. Useful when diagnosing "
            "wheel install issues or asset-resolution problems."
        ),
    )
    p.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit a JSON report instead of human-readable text.",
    )


def _build_version_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "version",
        help="Print the AsyncViz package version.",
        description="Print the resolved AsyncViz version.",
    )
    p.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit a JSON object with version + build identity.",
    )


# ── Namespace → typed config ───────────────────────────────────────────


def parse(argv: list[str] | None = None) -> tuple[ParsedCommand, argparse.Namespace]:
    """Parse ``argv`` and return the typed command + raw namespace.

    Returning the namespace alongside the typed view lets commands
    that don't need the full :class:`RunCliConfig` (``doctor``,
    ``version``) read their own flags directly without forcing
    argparse output into a bespoke dataclass per command.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command
    if command is None:
        # No subcommand → print top-level help and exit 2 (usage error).
        parser.print_help()
        raise SystemExit(2)
    if command == "run":
        return ParsedCommand(command="run", run_config=_run_namespace_to_config(args)), args
    if command == "record":
        return ParsedCommand(command="record", run_config=_record_namespace_to_config(args)), args
    if command == "replay":
        return (
            ParsedCommand(command="replay", replay_config=_replay_namespace_to_config(args)),
            args,
        )
    if command in ("doctor", "version"):
        return ParsedCommand(command=command), args
    # Unreachable — argparse already enforces the choice set.
    raise SystemExit(2)


def _replay_namespace_to_config(args: argparse.Namespace) -> ReplayCliConfig:
    bundle: Path = args.bundle
    return ReplayCliConfig(
        bundle_path=bundle,
        host=args.host,
        port=args.port,
        browser=args.browser,
        startup_timeout=args.startup_timeout,
        speed=float(args.speed),
        autoplay=bool(args.autoplay),
        verify_integrity=bool(args.verify_integrity),
        rebuild_manifest_if_missing=bool(args.rebuild_manifest_if_missing),
        debug=args.debug,
        log_level=args.log_level,
        quiet=args.quiet,
    )


def _run_namespace_to_config(args: argparse.Namespace) -> RunCliConfig:
    # Manual mutex check — argparse's mutex group + REMAINDER fights
    # each other. When ``-m pkg`` is given, anything captured as
    # ``script`` is actually a user argv head (the parser couldn't
    # know).
    if args.module is not None and args.script is not None:
        # The positional we collected belongs to ``target_argv``,
        # not to ``script``. Prepend it back.
        args.target_argv = [args.script, *(args.target_argv or [])]
        args.script = None
    if args.module is None and args.script is None:
        raise SystemExit("asyncviz run: must specify a script or use -m MODULE")

    raw_argv: list[str] = list(args.target_argv or [])
    # argparse keeps the literal ``--`` separator at the head of the
    # remainder — drop it so the target doesn't see our delimiter.
    if raw_argv and raw_argv[0] == "--":
        raw_argv = raw_argv[1:]

    if args.module is not None:
        target = TargetSpec(
            kind="module",
            value=args.module,
            # ``python -m pkg.module`` sets argv[0] to the resolved
            # module path; we set it to the module name (best-effort)
            # so the target sees something predictable.
            argv=(args.module, *raw_argv),
        )
    else:
        assert args.script is not None  # narrowed above
        target = TargetSpec(
            kind="script",
            value=args.script,
            argv=(args.script, *raw_argv),
        )

    env_overrides: list[tuple[str, str]] = []
    for raw in args.env:
        if "=" not in raw:
            raise SystemExit(
                f"asyncviz run: --env requires KEY=VALUE form, got: {raw!r}",
            )
        key, _, value = raw.partition("=")
        env_overrides.append((key, value))

    return RunCliConfig(
        target=target,
        host=args.host,
        port=args.port,
        browser=args.browser,
        startup_timeout=args.startup_timeout,
        shutdown_timeout=args.shutdown_timeout,
        python_executable=args.python_executable,
        debug=args.debug,
        enable_instrumentation=not args.no_instrumentation,
        log_level=args.log_level,
        cwd=args.cwd,
        env_overrides=tuple(env_overrides),
        quiet=args.quiet,
        no_dashboard=args.no_dashboard,
    )


def _record_namespace_to_config(args: argparse.Namespace) -> RunCliConfig:
    """Compose a :class:`RunCliConfig` with recording enabled.

    The recording subcommand mirrors ``run`` for the launch knobs +
    layers the replay-recorder flags on top. We round-trip through
    :func:`_run_namespace_to_config` to share the target-resolution
    logic, then attach the recording options.
    """
    base = _run_namespace_to_config(args)
    output = _resolve_output_path(args.output)
    recording = RecordingOptions(
        enabled=True,
        output_path=output,
        compression=args.compress,
        chunk_events=int(args.chunk_events),
        chunk_bytes=int(args.chunk_bytes),
        queue_capacity=int(args.queue_capacity),
        flush_interval_seconds=float(args.flush_interval),
        include_event_types=(tuple(args.include_event) if args.include_event else None),
        exclude_event_types=tuple(args.exclude_event or ()),
        metadata_overrides=tuple(_parse_meta_pairs(args.meta)),
        capture_runtime_snapshot=not args.no_runtime_snapshot,
        capture_warning_snapshot=not args.no_warning_snapshot,
        backpressure=args.backpressure,
    )
    # ``replace`` would be cleaner but the dataclass is frozen; build
    # a fresh instance via the standard constructor with the recording
    # field overridden.
    from dataclasses import replace

    return replace(base, recording=recording)


def _resolve_output_path(value: Path | None) -> Path:
    from datetime import UTC, datetime

    if value is not None:
        return value
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path("asyncviz-recordings") / f"session-{stamp}.avz"


def _parse_meta_pairs(values: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for raw in values or []:
        if "=" not in raw:
            raise SystemExit(
                f"asyncviz record: --meta requires KEY=VALUE form, got: {raw!r}",
            )
        key, _, value = raw.partition("=")
        out.append((key, value))
    return out
