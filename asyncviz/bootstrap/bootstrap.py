from __future__ import annotations

import contextlib
import threading
import time

import uvicorn

from asyncviz.bootstrap.browser import open_browser_safely
from asyncviz.bootstrap.config import resolve_config
from asyncviz.bootstrap.runtime import AsyncVizRuntime
from asyncviz.bootstrap.services import ServiceContainer
from asyncviz.bootstrap.validation import (
    StartupTimeoutError,
    check_frontend_mode,
    check_port_available,
    validate_config,
)
from asyncviz.config import AsyncVizConfig, FrontendMode, LogLevel
from asyncviz.dashboard.app import STATIC_DIR
from asyncviz.dashboard.runner import build_server
from asyncviz.utils.logging import get_logger, setup_logging

logger = get_logger("bootstrap")


class _BootstrapState:
    """Thread-safe holder for the currently-running :class:`AsyncVizRuntime`.

    All transitions go through one lock so concurrent ``start()`` calls
    collapse to a single in-flight bootstrap, and ``stop()`` is always
    serialized against startup.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runtime: AsyncVizRuntime | None = None

    def start(self, config: AsyncVizConfig) -> AsyncVizRuntime:
        with self._lock:
            if self._runtime is not None and self._runtime.is_running:
                logger.warning(
                    "AsyncViz is already running at %s; ignoring start()",
                    self._runtime.dashboard_url,
                )
                return self._runtime

            # Pre-flight: fail fast with a clear message before we touch threads.
            check_frontend_mode(config, STATIC_DIR)
            check_port_available(config.host, config.port)

            logger.info("Starting AsyncViz on %s", config.dashboard_url)
            services = ServiceContainer.build(config)
            server = build_server(services.app, config)
            thread = threading.Thread(target=server.run, name="asyncviz-server", daemon=True)
            thread.start()

            if not _wait_until_ready(server, timeout=config.startup_timeout):
                _abort_after_failed_start(server, thread)
                raise StartupTimeoutError(
                    f"AsyncViz server did not become ready within {config.startup_timeout:.1f}s"
                )

            runtime = AsyncVizRuntime(
                config=config,
                services=services,
                started_at=time.time(),
                server=server,
                thread=thread,
            )
            self._runtime = runtime
            logger.info("AsyncViz dashboard available at %s", runtime.dashboard_url)

            if config.open_browser:
                open_browser_safely(runtime.dashboard_url)
            return runtime

    def stop(self) -> None:
        with self._lock:
            runtime = self._runtime
            if runtime is None:
                return
            if runtime.is_running:
                logger.info("Stopping AsyncViz")
                runtime.shutdown()
            self._runtime = None

    def is_running(self) -> bool:
        runtime = self._runtime
        return runtime is not None and runtime.is_running

    def get(self) -> AsyncVizRuntime | None:
        runtime = self._runtime
        if runtime is None or not runtime.is_running:
            return None
        return runtime


# Module-level singleton. The class hides every transition behind a lock,
# so this is the only mutable global in the bootstrap layer.
_state = _BootstrapState()


def start(
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
) -> AsyncVizRuntime:
    """Launch the embedded AsyncViz dashboard and return the live runtime.

    Configuration precedence: ``kwargs`` > environment variables > defaults.
    Safe to call repeatedly — subsequent calls log a warning and return the
    already-running runtime.
    """
    config = resolve_config(
        host=host,
        port=port,
        open_browser=open_browser,
        debug=debug,
        heartbeat_interval=heartbeat_interval,
        frontend_mode=frontend_mode,
        log_level=log_level,
        startup_timeout=startup_timeout,
        enable_instrumentation=enable_instrumentation,
    )
    validate_config(config)
    setup_logging(debug=config.debug)
    return _state.start(config)


def stop() -> None:
    """Shut down the running AsyncViz runtime, if any. Always safe to call."""
    _state.stop()


def is_running() -> bool:
    """Return True if an AsyncViz runtime is currently serving requests."""
    return _state.is_running()


def get_runtime() -> AsyncVizRuntime | None:
    """Return the current :class:`AsyncVizRuntime`, or ``None`` when not running."""
    return _state.get()


def _wait_until_ready(server: uvicorn.Server, *, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.started:
            return True
        time.sleep(0.05)
    return False


def _abort_after_failed_start(server: uvicorn.Server, thread: threading.Thread) -> None:
    server.should_exit = True
    with contextlib.suppress(Exception):
        thread.join(timeout=2.0)
