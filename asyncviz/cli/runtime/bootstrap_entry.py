"""Subprocess-side bootstrap entry for ``asyncviz run``.

The CLI spawns the user's target via::

    python -m asyncviz.cli.runtime.bootstrap_entry

The bootstrap reads the run configuration from environment variables
(set by the parent CLI process), starts the AsyncViz runtime via the
canonical :func:`asyncviz.start`, executes the target script/module
via :mod:`runpy`, and ensures :func:`asyncviz.stop` runs on the way
out so the dashboard shuts cleanly.

This module is intentionally hermetic — it only imports asyncviz +
stdlib at module load. That keeps the spawned subprocess cold-start
fast and free of third-party state.
"""

from __future__ import annotations

import json
import os
import runpy
import sys
from dataclasses import dataclass
from typing import Literal

BOOTSTRAP_ENV_PREFIX = "ASYNCVIZ_CLI_"

_ENV_TARGET_KIND = f"{BOOTSTRAP_ENV_PREFIX}TARGET_KIND"
_ENV_TARGET_VALUE = f"{BOOTSTRAP_ENV_PREFIX}TARGET_VALUE"
_ENV_TARGET_ARGV = f"{BOOTSTRAP_ENV_PREFIX}TARGET_ARGV_JSON"
_ENV_DASHBOARD_HOST = f"{BOOTSTRAP_ENV_PREFIX}DASHBOARD_HOST"
_ENV_DASHBOARD_PORT = f"{BOOTSTRAP_ENV_PREFIX}DASHBOARD_PORT"
_ENV_START_DASHBOARD = f"{BOOTSTRAP_ENV_PREFIX}START_DASHBOARD"
_ENV_ENABLE_INSTRUMENTATION = f"{BOOTSTRAP_ENV_PREFIX}ENABLE_INSTRUMENTATION"
_ENV_DEBUG = f"{BOOTSTRAP_ENV_PREFIX}DEBUG"
_ENV_LOG_LEVEL = f"{BOOTSTRAP_ENV_PREFIX}LOG_LEVEL"
_ENV_STARTUP_TIMEOUT = f"{BOOTSTRAP_ENV_PREFIX}STARTUP_TIMEOUT"
_ENV_RECORDING_JSON = f"{BOOTSTRAP_ENV_PREFIX}RECORDING_JSON"

TargetKind = Literal["script", "module"]


@dataclass(frozen=True, slots=True)
class BootstrapTargetSpec:
    """Subprocess-side view of the target."""

    kind: TargetKind
    value: str
    argv: tuple[str, ...]


# ── Env (de)serialization ──────────────────────────────────────────────


def _env_for_config(
    *,
    target_kind: TargetKind,
    target_value: str,
    target_argv: tuple[str, ...],
    host: str,
    port: int,
    start_dashboard: bool,
    enable_instrumentation: bool,
    debug: bool,
    log_level: str | None,
    startup_timeout: float,
) -> dict[str, str]:
    """Encode the run config as env vars the subprocess can read."""
    env: dict[str, str] = {
        _ENV_TARGET_KIND: target_kind,
        _ENV_TARGET_VALUE: target_value,
        _ENV_TARGET_ARGV: json.dumps(list(target_argv)),
        _ENV_DASHBOARD_HOST: host,
        _ENV_DASHBOARD_PORT: str(port),
        _ENV_START_DASHBOARD: "1" if start_dashboard else "0",
        _ENV_ENABLE_INSTRUMENTATION: "1" if enable_instrumentation else "0",
        _ENV_DEBUG: "1" if debug else "0",
        _ENV_STARTUP_TIMEOUT: str(startup_timeout),
    }
    if log_level is not None:
        env[_ENV_LOG_LEVEL] = log_level
    return env


def encode_bootstrap_env(config: object) -> dict[str, str]:
    """Public helper used by :mod:`process_environment` to build env."""
    # Import here to avoid a circular at module load.
    from asyncviz.cli.configuration import RunCliConfig

    if not isinstance(config, RunCliConfig):
        raise TypeError(f"expected RunCliConfig, got {type(config).__name__}")
    env = _env_for_config(
        target_kind=config.target.kind,
        target_value=config.target.value,
        target_argv=config.target.argv,
        host=config.host,
        port=config.port,
        start_dashboard=not config.no_dashboard,
        enable_instrumentation=config.enable_instrumentation,
        debug=config.debug,
        log_level=config.log_level,
        startup_timeout=config.startup_timeout,
    )
    if config.recording.enabled and config.recording.output_path is not None:
        env[_ENV_RECORDING_JSON] = json.dumps(
            {
                "output_path": str(config.recording.output_path),
                "compression": config.recording.compression,
                "chunk_events": config.recording.chunk_events,
                "chunk_bytes": config.recording.chunk_bytes,
                "queue_capacity": config.recording.queue_capacity,
                "flush_interval_seconds": config.recording.flush_interval_seconds,
                "include_event_types": (
                    list(config.recording.include_event_types)
                    if config.recording.include_event_types is not None
                    else None
                ),
                "exclude_event_types": list(config.recording.exclude_event_types),
                "metadata_overrides": [list(p) for p in config.recording.metadata_overrides],
                "capture_runtime_snapshot": config.recording.capture_runtime_snapshot,
                "capture_warning_snapshot": config.recording.capture_warning_snapshot,
                "backpressure": config.recording.backpressure,
            },
        )
    return env


def _read_target() -> BootstrapTargetSpec:
    kind = os.environ.get(_ENV_TARGET_KIND)
    value = os.environ.get(_ENV_TARGET_VALUE)
    argv_raw = os.environ.get(_ENV_TARGET_ARGV, "[]")
    if kind not in ("script", "module") or not value:
        raise SystemExit(
            f"asyncviz: bootstrap entry missing target environment "
            f"({_ENV_TARGET_KIND}/{_ENV_TARGET_VALUE})",
        )
    try:
        argv = tuple(json.loads(argv_raw))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"asyncviz: invalid {_ENV_TARGET_ARGV}: {exc}") from None
    return BootstrapTargetSpec(kind=kind, value=value, argv=argv)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y", "t"}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# ── Entry point ────────────────────────────────────────────────────────


def cli_bootstrap_main() -> int:
    """Subprocess entry point.

    Starts the runtime (when requested) + runs the target + ensures
    a clean shutdown. SystemExit propagates from inside the target so
    Python's normal exit-code semantics apply.
    """
    # Import asyncviz only after we've read the env, so a missing env
    # error doesn't hide behind an import failure if asyncviz itself
    # is broken.
    target = _read_target()

    start_dashboard = _env_bool(_ENV_START_DASHBOARD, True)
    enable_instrumentation = _env_bool(_ENV_ENABLE_INSTRUMENTATION, True)
    debug = _env_bool(_ENV_DEBUG, False)
    startup_timeout = _env_float(_ENV_STARTUP_TIMEOUT, 5.0)
    host = os.environ.get(_ENV_DASHBOARD_HOST, "127.0.0.1")
    port = int(os.environ.get(_ENV_DASHBOARD_PORT, "8877"))
    log_level = os.environ.get(_ENV_LOG_LEVEL)

    runtime = None
    recorder = None
    if start_dashboard or enable_instrumentation:
        # ``asyncviz.start`` is idempotent: even if instrumentation
        # alone is requested we still need to call start() so the
        # patcher attaches. Pass ``no-frontend`` shape via the
        # ``frontend_mode`` if the dashboard is disabled; the dashboard
        # currently doesn't have a "headless" config, so we run a
        # normal start either way and ignore the URL when
        # ``start_dashboard`` is false.
        import asyncviz

        try:
            runtime = asyncviz.start(
                host=host,
                port=port,
                open_browser=False,
                debug=debug,
                log_level=log_level,  # type: ignore[arg-type]
                enable_instrumentation=enable_instrumentation,
                startup_timeout=startup_timeout,
            )
        except Exception as exc:
            print(f"asyncviz: bootstrap failed: {exc}", file=sys.stderr, flush=True)
            return 10  # ExitCode.BOOTSTRAP_FAILURE

        # Optional replay recording — must start *after* the runtime
        # so the recorder can subscribe to the live state-store stream.
        recording_raw = os.environ.get(_ENV_RECORDING_JSON)
        if recording_raw and runtime is not None:
            try:
                recorder = _start_recording_from_env(
                    runtime=runtime,
                    recording_raw=recording_raw,
                    target=target,
                    host=host,
                    port=port,
                )
            except Exception as exc:  # pragma: no cover — defensive
                print(
                    f"asyncviz: recording bootstrap failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )

    # Install the loop-discovery hook before the target runs. When the
    # target calls ``asyncio.run(main())`` the policy intercepts the
    # new loop and hands its reference to the lag monitor. Without
    # this, the lag monitor would sample the dashboard's uvicorn loop
    # — which never blocks — and the blocking-warning pipeline would
    # never fire on a real user workload.
    loop_discovery_handle = None
    if runtime is not None:
        loop_discovery_handle = _install_lag_monitor_loop_discovery(runtime)

    try:
        return _run_target(target)
    finally:
        if loop_discovery_handle is not None:
            try:
                loop_discovery_handle.uninstall()
            except Exception as exc:  # pragma: no cover — best-effort
                print(
                    f"asyncviz: loop-discovery uninstall error: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
        if recorder is not None:
            try:
                from asyncviz.runtime.replay.recorder import finalize_recorder

                finalize_recorder(recorder)
            except Exception as exc:  # pragma: no cover — best-effort
                print(f"asyncviz: recorder shutdown error: {exc}", file=sys.stderr, flush=True)
        if runtime is not None:
            try:
                import asyncviz

                asyncviz.stop()
            except Exception as exc:  # pragma: no cover — best-effort
                print(f"asyncviz: shutdown error: {exc}", file=sys.stderr, flush=True)


def _install_lag_monitor_loop_discovery(runtime: object) -> object | None:
    """Wire the lag monitor to the user's loop the moment it's created.

    Returns the policy handle so the caller can uninstall it during
    teardown. Returns ``None`` (and logs a warning) if the discovery
    hook can't be reached — the dashboard still works, blocking
    warnings just won't fire.
    """
    try:
        lag_monitor = runtime.services.lag_monitor  # type: ignore[attr-defined]
    except AttributeError:
        print(
            "asyncviz: lag monitor not available on runtime; "
            "blocking warnings disabled",
            file=sys.stderr,
            flush=True,
        )
        return None

    from asyncviz.cli.runtime.loop_discovery import install_main_thread_loop_discovery
    from asyncviz.utils.logging import get_logger

    logger = get_logger("cli.runtime.bootstrap")

    def _on_user_loop(loop: object) -> None:
        try:
            lag_monitor.bind_to_loop_threadsafe(loop)
            logger.info(
                "lag monitor bound to user loop (id=%s); "
                "blocking warnings now active",
                id(loop),
            )
        except Exception:
            logger.exception(
                "lag monitor failed to bind to user loop; "
                "blocking warnings disabled for this run",
            )

    return install_main_thread_loop_discovery(_on_user_loop)


def _run_target(target: BootstrapTargetSpec) -> int:
    """Execute the user's script or module + return its exit code."""
    # Splice the target argv into ``sys.argv`` so the target sees
    # exactly what Python would normally pass it.
    sys.argv = list(target.argv) if target.argv else [target.value]

    try:
        if target.kind == "script":
            # ``run_path`` with ``run_name="__main__"`` makes
            # ``if __name__ == "__main__":`` guards fire.
            runpy.run_path(target.value, run_name="__main__")
        else:
            # ``run_module`` with ``alter_sys=True`` sets
            # ``sys.argv[0]`` correctly + makes ``__name__`` ==
            # ``"__main__"`` for the module.
            runpy.run_module(target.value, run_name="__main__", alter_sys=True)
        return 0
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        # String/exception code → print and use generic failure.
        print(str(code), file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        return 130


def _start_recording_from_env(
    *,
    runtime: object,
    recording_raw: str,
    target: BootstrapTargetSpec,
    host: str,
    port: int,
) -> object | None:
    """Hydrate the recorder config from env JSON + start a session."""
    from pathlib import Path

    import asyncviz
    from asyncviz.runtime.replay.recorder import (
        BackpressureMode,
        CompressionMode,
        RecorderConfig,
        start_recorder_for_runtime,
    )
    from asyncviz.runtime.replay.recorder.replay_export import TargetDescription

    payload = json.loads(recording_raw)
    config = RecorderConfig(
        output_path=Path(payload["output_path"]),
        compression=CompressionMode(payload.get("compression", "gzip")),
        chunk_events=int(payload.get("chunk_events", 4096)),
        chunk_bytes=int(payload.get("chunk_bytes", 4 * 1024 * 1024)),
        queue_capacity=int(payload.get("queue_capacity", 16_384)),
        flush_interval_seconds=float(payload.get("flush_interval_seconds", 1.0)),
        include_event_types=(
            tuple(payload["include_event_types"])
            if payload.get("include_event_types")
            else None
        ),
        exclude_event_types=tuple(payload.get("exclude_event_types", [])),
        metadata_overrides=tuple(
            (str(k), str(v)) for k, v in payload.get("metadata_overrides", [])
        ),
        capture_runtime_snapshot=bool(payload.get("capture_runtime_snapshot", True)),
        capture_warning_snapshot=bool(payload.get("capture_warning_snapshot", True)),
        backpressure=BackpressureMode(payload.get("backpressure", "drop_newest")),
    )
    description = TargetDescription(
        kind=target.kind,
        value=target.value,
        argv=tuple(target.argv),
    )
    # Build a RuntimeOptions snapshot for embedding in the bundle
    # metadata so the on-disk artifact records the resolved config.
    try:
        from asyncviz.configuration import resolve_options

        runtime_options = resolve_options(environ=os.environ).options
    except Exception:  # pragma: no cover — defensive
        runtime_options = None

    return start_recorder_for_runtime(
        config,
        runtime=runtime,
        target=description,
        asyncviz_version=asyncviz.__version__,
        host=host,
        port=port,
        runtime_options=runtime_options,
    )


if __name__ == "__main__":
    sys.exit(cli_bootstrap_main())
