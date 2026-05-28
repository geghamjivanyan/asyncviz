"""Backwards-compatibility adapter between the canonical
:class:`RuntimeOptions` and the legacy
:class:`asyncviz.config.AsyncVizConfig`.

The bootstrap layer (and every existing caller) still consumes
:class:`AsyncVizConfig`. This adapter translates a fully-resolved
:class:`RuntimeOptions` into that legacy struct so the new options
layer plugs in without rewriting the bootstrap pipeline.
"""

from __future__ import annotations

from asyncviz.config import AsyncVizConfig
from asyncviz.configuration.runtime_options import RuntimeOptions


def to_legacy_config(options: RuntimeOptions) -> AsyncVizConfig:
    """Project ``options`` onto the legacy :class:`AsyncVizConfig`."""
    return AsyncVizConfig(
        host=options.network.host,
        port=options.network.port,
        open_browser=options.browser.policy != "never",
        debug=options.dashboard.debug,
        heartbeat_interval=options.dashboard.heartbeat_interval_seconds,
        frontend_mode=options.dashboard.frontend_mode,
        log_level=options.dashboard.log_level,
        startup_timeout=options.dashboard.startup_timeout_seconds,
        enable_instrumentation=options.monitoring.enable_instrumentation,
    )


def from_legacy_config(config: AsyncVizConfig) -> RuntimeOptions:
    """Project a legacy :class:`AsyncVizConfig` onto the canonical options.

    Useful for tests + the diagnostics endpoint that wants the new
    JSON shape even on code paths that still construct the legacy
    struct directly.
    """
    from asyncviz.configuration.runtime_browser import BrowserOptions
    from asyncviz.configuration.runtime_dashboard import DashboardOptions
    from asyncviz.configuration.runtime_monitoring import MonitoringOptions
    from asyncviz.configuration.runtime_network import NetworkOptions

    return RuntimeOptions(
        network=NetworkOptions(host=config.host, port=config.port),
        dashboard=DashboardOptions(
            debug=config.debug,
            heartbeat_interval_seconds=config.heartbeat_interval,
            startup_timeout_seconds=config.startup_timeout,
            log_level=config.log_level,
            frontend_mode=config.frontend_mode,
        ),
        browser=BrowserOptions(policy="auto" if config.open_browser else "never"),
        monitoring=MonitoringOptions(enable_instrumentation=config.enable_instrumentation),
    )
