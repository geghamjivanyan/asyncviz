"""Top-level orchestrator for ``asyncviz replay``.

Conceptually a sibling of :mod:`asyncviz.cli.runtime.launcher` (which
orchestrates ``asyncviz run``), but the runtime shape is different:
there is no subprocess + no live instrumentation. The dashboard runs
in-process with instrumentation disabled, the replay engine streams
recorded events over the dashboard's existing websocket fan-out via
:class:`DashboardReplaySink`, and the operator drives playback from
the SPA.

Responsibilities:

* validate the bundle + open it through :class:`ReplayEventLoader`
* spin the dashboard up via :func:`asyncviz.start` with instrumentation
  off so no lag monitor or asyncio patcher ever activates
* discover the dashboard's loop reference (published by the lifespan
  as ``app.state.dashboard_loop``) so the sink can hop cross-thread
* construct :class:`ReplayRuntimeEngine` against the loader + sink
* optionally open a browser tab
* run the playback loop until the recording exhausts or the user
  sends SIGINT/SIGTERM, then clean shutdown
"""

from __future__ import annotations

import asyncio
import signal
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from asyncviz.cli.browser import (
    BrowserLaunchConfig,
    BrowserLauncher,
    build_dashboard_url,
)
from asyncviz.cli.configuration import ReplayCliConfig
from asyncviz.cli.exit_codes import ExitCode
from asyncviz.cli.output import error, info, log, ok
from asyncviz.cli.runtime.diagnostics import record_lifecycle_event
from asyncviz.cli.runtime.replay_bundle_adapter import RecorderBundleAdapter
from asyncviz.dashboard.replay import DashboardReplaySink
from asyncviz.dashboard.replay.replay_marker_derivation import (
    derive_markers_and_bookmarks,
)
from asyncviz.dashboard.replay.replay_status_broadcaster import (
    ReplayRecordingMetadata,
    ReplayStatusBroadcaster,
)
from asyncviz.replay.loading import (
    ReplayEventLoader,
    ReplayLoaderConfig,
)
from asyncviz.replay.runtime import (
    ReplayEngineConfig,
    ReplayRuntimeEngine,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("cli.runtime.replay_launcher")

_DEFAULT_DASHBOARD_LOOP_TIMEOUT_SECONDS: float = 5.0


@dataclass(frozen=True, slots=True)
class ReplayLauncherOutcome:
    """End-state surfaced to :func:`asyncviz.cli.commands.replay.run`."""

    exit_code: int
    dashboard_url: str | None
    frames_emitted: int


def run_replay(config: ReplayCliConfig) -> ReplayLauncherOutcome:
    """Synchronous CLI entry. Owns the asyncio.run for the engine.

    Returns a :class:`ReplayLauncherOutcome` whose exit code maps to
    the OS-level return code the dispatcher hands to ``sys.exit``.
    """
    bundle_path = _validate_bundle(config.bundle_path)
    if bundle_path is None:
        return ReplayLauncherOutcome(
            exit_code=int(ExitCode.CONFIGURATION_ERROR),
            dashboard_url=None,
            frames_emitted=0,
        )

    if not config.quiet:
        _emit_banner(bundle_path, config)

    try:
        return asyncio.run(_run_async(bundle_path, config))
    except KeyboardInterrupt:
        return ReplayLauncherOutcome(
            exit_code=int(ExitCode.INTERRUPTED),
            dashboard_url=config.dashboard_url,
            frames_emitted=0,
        )


# ── internals ──────────────────────────────────────────────────────────


def _validate_bundle(path: Path) -> Path | None:
    resolved = path.resolve()
    if not resolved.exists():
        error(f"replay: bundle not found: {resolved}")
        return None
    if not resolved.is_dir():
        error(
            f"replay: bundle must be a directory (.avz layout): {resolved}\n"
            "  Hint: 'asyncviz record' writes a directory like "
            "asyncviz-recordings/session-<timestamp>.avz/.",
        )
        return None
    manifest = resolved / "manifest.json"
    if not manifest.is_file():
        error(
            f"replay: bundle missing manifest.json: {resolved}\n"
            "  Re-run with --rebuild-manifest to scan + synthesize one "
            "from the chunks (only safe on partially-finalized recordings).",
        )
        return None
    return resolved


def _emit_banner(bundle: Path, config: ReplayCliConfig) -> None:
    log("AsyncViz · replay")
    info(f"bundle       {bundle}")
    info(f"dashboard    {config.dashboard_url}")
    info(f"speed        {config.speed}x")
    info(f"autoplay     {config.autoplay}")
    info(f"integrity    {'on' if config.verify_integrity else 'off'}")


async def _run_async(
    bundle: Path,
    config: ReplayCliConfig,
) -> ReplayLauncherOutcome:
    record_lifecycle_event("replay-open", str(bundle))
    loader, summary_text, metadata, markers, bookmarks = _open_bundle(
        bundle,
        config,
    )
    if not config.quiet:
        info(f"recording    {summary_text}")
        info(f"bundle_id    {metadata.bundle_id}")
        info(f"runtime_id   {metadata.runtime_id or '<unknown>'}")
        info(
            f"timeline     {len(markers)} markers, {len(bookmarks)} bookmarks",
        )

    # Spin the dashboard. Instrumentation OFF — replay sources its
    # events from the loader, never from a live workload. The browser
    # auto-open hook below honours the operator's --browser preference.
    import asyncviz

    runtime = asyncviz.start(
        host=config.host,
        port=config.port,
        open_browser=False,  # We launch via BrowserLauncher below.
        debug=config.debug,
        log_level=config.log_level,  # type: ignore[arg-type]
        enable_instrumentation=False,
        startup_timeout=config.startup_timeout,
    )
    dashboard_url = build_dashboard_url(host=config.host, port=config.port)

    sink: DashboardReplaySink | None = None
    engine: ReplayRuntimeEngine | None = None
    broadcaster: ReplayStatusBroadcaster | None = None
    play_task: asyncio.Task[None] | None = None
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    try:
        dashboard_loop = await _await_dashboard_loop(runtime, config.startup_timeout)
        if dashboard_loop is None:
            error("replay: dashboard never published its event loop reference")
            return ReplayLauncherOutcome(
                exit_code=int(ExitCode.BOOTSTRAP_FAILURE),
                dashboard_url=dashboard_url,
                frames_emitted=0,
            )

        sink = DashboardReplaySink(
            manager=runtime.services.websocket_manager,
            dashboard_loop=dashboard_loop,
        )
        engine = ReplayRuntimeEngine(
            loader=loader,
            config=ReplayEngineConfig(initial_speed=config.speed),
            sink=sink,
        )

        # The frontend's replay timeline needs the session window +
        # bundle metadata BEFORE the first runtime_event lands, or it
        # renders "NO RECORDING LOADED" forever. The broadcaster
        # emits the initial ``replay_status`` synchronously in
        # ``start()`` and a deduplicated stream of updates on a
        # ~0.5 s cadence after that.
        broadcaster = ReplayStatusBroadcaster(
            engine=engine,
            metadata=metadata,
            manager=runtime.services.websocket_manager,
            dashboard_loop=dashboard_loop,
            markers=markers,
            bookmarks=bookmarks,
        )
        await broadcaster.start()

        # Optional browser open — fire-and-forget, the launcher's
        # internal thread handles the readiness probe.
        if config.browser != "never":
            _open_browser_async(config=config, url=dashboard_url)

        # Pause-first when --no-autoplay so the dashboard hydrates
        # against the engine's initial state but no frames flow until
        # the operator hits Play.
        if not config.autoplay:
            await engine.pause()

        if not config.quiet:
            ok(f"dashboard ready at {dashboard_url}")
            log("playback starting — Ctrl-C to stop")

        # ``engine.play()`` returns after kicking off the internal
        # playback task; it does NOT await frame drain. We await
        # ``wait_until_done`` so the launcher blocks for the actual
        # duration of the replay (or until the user signals shutdown).
        await engine.play()
        play_task = asyncio.create_task(
            engine.wait_until_done(),
            name="asyncviz-replay-wait",
        )
        await _wait_for_completion(play_task, stop_event)

        frames = sink.frames_pushed
        if not config.quiet:
            ok(f"replay finished — {frames} frames emitted")
        return ReplayLauncherOutcome(
            exit_code=int(ExitCode.OK),
            dashboard_url=dashboard_url,
            frames_emitted=frames,
        )
    finally:
        if play_task is not None and not play_task.done():
            play_task.cancel()
            with suppress(BaseException):
                await play_task
        if engine is not None:
            with suppress(BaseException):
                await engine.stop()
        if broadcaster is not None:
            with suppress(BaseException):
                await broadcaster.stop()
        with suppress(BaseException):
            loader.close()
        with suppress(BaseException):
            asyncviz.stop()


def _open_bundle(
    bundle: Path,
    config: ReplayCliConfig,
) -> tuple[
    object,
    str,
    ReplayRecordingMetadata,
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """Open ``bundle`` through the most compatible reader available.

    Prefers :class:`ReplayEventLoader` (the canonical reader for the
    forward-looking bundle schema). When the manifest is in the
    recorder's legacy ``bundle_id``-keyed shape — the format
    ``asyncviz record`` writes today — falls back to
    :class:`RecorderBundleAdapter` so the launcher still streams
    frames to the dashboard. The fallback is logged at INFO so the
    drift is visible.

    Returns ``(loader_like, summary_text, metadata, markers, bookmarks)``.
    The metadata + markers + bookmarks travel to
    :class:`ReplayStatusBroadcaster` so the SPA can render bundle
    identity, session-window bounds, and timeline annotations without
    requiring a separate envelope or a record-time mutation of the
    bundle format.
    """
    loader_config = ReplayLoaderConfig(
        session_dir=bundle,
        verify_integrity=config.verify_integrity,
    )
    try:
        canonical = ReplayEventLoader.open(
            bundle,
            config=loader_config,
            rebuild_manifest_if_missing=config.rebuild_manifest_if_missing,
        )
        summary = canonical.summary()
        metadata = ReplayRecordingMetadata(
            bundle_id=summary.recording_id,
            runtime_id=summary.runtime_id,
            event_count=summary.event_count,
            chunk_count=summary.chunk_count,
            snapshot_count=summary.snapshot_count,
            last_sequence=summary.last_sequence,
            finalized=summary.finalized,
            source_label=str(bundle),
        )
        markers, bookmarks = _derive_canonical_metadata(canonical)
        return (
            canonical,
            (
                f"{summary.event_count} events "
                f"in {summary.chunk_count} chunks "
                f"({summary.snapshot_count} snapshot frames)"
            ),
            metadata,
            markers,
            bookmarks,
        )
    except Exception as exc:
        logger.info(
            "canonical ReplayEventLoader rejected bundle (%s); "
            "falling back to RecorderBundleAdapter",
            exc,
        )
        adapter = RecorderBundleAdapter.open(bundle)
        summary = adapter.summary()
        metadata = ReplayRecordingMetadata(
            bundle_id=summary.bundle_id,
            runtime_id=summary.runtime_id,
            event_count=summary.event_count,
            chunk_count=summary.chunk_count,
            snapshot_count=summary.snapshot_count,
            last_sequence=summary.last_sequence,
            finalized=summary.finalized,
            source_label=str(bundle),
        )
        markers, bookmarks = adapter.derive_timeline_metadata()
        return (
            adapter,
            (
                f"{summary.event_count} events "
                f"in {summary.chunk_count} chunks "
                f"({summary.snapshot_count} snapshot files) "
                f"[recorder-format bundle]"
            ),
            metadata,
            markers,
            bookmarks,
        )


def _derive_canonical_metadata(
    canonical: ReplayEventLoader,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Project canonical-loader frames into the dict shape the
    derivation module expects.

    Only ``runtime_event`` frames carry classify-able event types — we
    skip ``snapshot`` / ``cursor`` frames silently.
    """
    projected = (
        {
            "sequence": frame.sequence,
            "monotonic_ns": frame.monotonic_ns,
            "event_type": frame.payload_type,
            "payload": frame.payload,
        }
        for frame in canonical.iter_frames()
        if frame.frame_type == "runtime_event"
    )
    return derive_markers_and_bookmarks(projected)


async def _await_dashboard_loop(
    runtime: object,
    timeout: float,  # noqa: ASYNC109 — deliberate bound; we return None on expiry instead of raising
) -> asyncio.AbstractEventLoop | None:
    """Poll ``app.state.dashboard_loop`` until the lifespan publishes it.

    The lifespan stashes the value as one of its first actions, so
    this normally returns within a few ms of dashboard startup. Bounded
    by ``timeout`` so a misbehaving dashboard doesn't hang the launcher.
    """
    deadline = time.monotonic() + max(timeout, _DEFAULT_DASHBOARD_LOOP_TIMEOUT_SECONDS)
    while time.monotonic() < deadline:
        try:
            services = runtime.services  # type: ignore[attr-defined]
            loop = services.app.state.dashboard_loop  # type: ignore[attr-defined]
        except AttributeError:
            loop = None
        if loop is not None:
            return loop  # type: ignore[no-any-return]
        await asyncio.sleep(0.025)
    return None


async def _wait_for_completion(
    play_task: asyncio.Task[None],
    stop_event: asyncio.Event,
) -> None:
    stop_waiter = asyncio.create_task(stop_event.wait(), name="asyncviz-replay-stop")
    try:
        done, _pending = await asyncio.wait(
            {play_task, stop_waiter},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if stop_waiter in done and not play_task.done():
            play_task.cancel()
            with suppress(BaseException):
                await play_task
    finally:
        if not stop_waiter.done():
            stop_waiter.cancel()
            with suppress(BaseException):
                await stop_waiter


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def _handler() -> None:
        if not stop_event.is_set():
            log("replay: shutdown signal received")
            stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, _handler)


def _open_browser_async(*, config: ReplayCliConfig, url: str) -> None:
    """Schedule the readiness-probed browser open on a daemon thread."""
    policy = config.browser
    launch_config = BrowserLaunchConfig(
        url=url,
        # ``BrowserLaunchPolicy`` mirrors the ``--browser`` choice set
        # exactly; reusing the string via .upper() keeps the parser
        # free of policy-specific imports.
        policy=_policy_from_string(policy),
        readiness_url=f"{url.rstrip('/')}/api/health/live",
    )
    BrowserLauncher().launch_async(launch_config)


def _policy_from_string(value: str):
    from asyncviz.cli.browser import BrowserLaunchPolicy

    return BrowserLaunchPolicy(value)
