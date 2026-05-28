"""Browser launch + detection helpers for the CLI.

Lives in the CLI package (not in ``asyncviz.bootstrap``) because the
CLI has its own UX needs — printing a "opened in browser" line,
honouring the ``--browser`` tri-state, supporting headless-CI
environments. The bootstrap helper at
:func:`asyncviz.bootstrap.browser.open_browser_safely` stays
canonical for ``asyncviz.start()`` calls from Python code.

The module is split into focused concerns so each piece is unit-
testable in isolation: availability detection, policy resolution,
preferences, readiness probing, the platform process call, session
dedup, backpressure, observability.
"""

from asyncviz.cli.browser.browser_availability import (
    AvailabilityCode,
    BrowserAvailability,
)
from asyncviz.cli.browser.browser_backpressure import (
    DEFAULT_MAX_CONCURRENT_LAUNCHES,
    BrowserBackpressureGuard,
    get_default_backpressure_guard,
    reset_default_backpressure_guard,
)
from asyncviz.cli.browser.browser_configuration import (
    DEFAULT_LAUNCH_DELAY_SECONDS,
    DEFAULT_LAUNCH_TIMEOUT_SECONDS,
    DEFAULT_READINESS_INTERVAL_SECONDS,
    DEFAULT_READINESS_TIMEOUT_SECONDS,
    BrowserLaunchConfig,
)
from asyncviz.cli.browser.browser_detection import (
    BrowserPreference,
    detect_browser_availability,
    should_open_browser,
)
from asyncviz.cli.browser.browser_diagnostics import (
    BrowserDiagnosticsSnapshot,
    build_browser_diagnostics,
    get_last_launch,
    record_last_launch,
    reset_last_launch,
)
from asyncviz.cli.browser.browser_launcher import (
    BrowserLauncher,
    BrowserLaunchOutcome,
    launch_browser,
)
from asyncviz.cli.browser.browser_metrics import (
    BrowserMetricsSnapshot,
    get_browser_metrics,
    reset_browser_metrics,
)
from asyncviz.cli.browser.browser_policy import (
    BrowserLaunchPolicy,
    PolicyDecision,
    decide,
    resolve_policy,
)
from asyncviz.cli.browser.browser_preferences import (
    ENV_BROWSER_POLICY,
    ENV_NO_BROWSER,
    BrowserPreferences,
    load_preferences,
)
from asyncviz.cli.browser.browser_process import (
    BrowserBackend,
    NoopBackend,
    ProcessLaunchOutcome,
    StubBackend,
    WebbrowserBackend,
    default_backend,
)
from asyncviz.cli.browser.browser_readiness import (
    ProbeOutcome,
    ProbeOutcomeKind,
    ReadinessProbe,
)
from asyncviz.cli.browser.browser_sessions import (
    BrowserSessionGuard,
    get_default_session_guard,
    reset_default_session_guard,
)
from asyncviz.cli.browser.browser_statistics import (
    LaunchStatistics,
    LaunchStatus,
)
from asyncviz.cli.browser.browser_tracing import (
    BrowserTraceEntry,
    BrowserTraceKind,
    clear_browser_trace,
    get_browser_trace,
    is_browser_trace_enabled,
    record_browser_trace,
    set_browser_trace_enabled,
)
from asyncviz.cli.browser.browser_urls import build_dashboard_url

__all__ = [
    "DEFAULT_LAUNCH_DELAY_SECONDS",
    "DEFAULT_LAUNCH_TIMEOUT_SECONDS",
    "DEFAULT_MAX_CONCURRENT_LAUNCHES",
    "DEFAULT_READINESS_INTERVAL_SECONDS",
    "DEFAULT_READINESS_TIMEOUT_SECONDS",
    "ENV_BROWSER_POLICY",
    "ENV_NO_BROWSER",
    "AvailabilityCode",
    "BrowserAvailability",
    "BrowserBackend",
    "BrowserBackpressureGuard",
    "BrowserDiagnosticsSnapshot",
    "BrowserLaunchConfig",
    "BrowserLaunchOutcome",
    "BrowserLaunchPolicy",
    "BrowserLauncher",
    "BrowserMetricsSnapshot",
    "BrowserPreference",
    "BrowserPreferences",
    "BrowserSessionGuard",
    "BrowserTraceEntry",
    "BrowserTraceKind",
    "LaunchStatistics",
    "LaunchStatus",
    "NoopBackend",
    "PolicyDecision",
    "ProbeOutcome",
    "ProbeOutcomeKind",
    "ProcessLaunchOutcome",
    "ReadinessProbe",
    "StubBackend",
    "WebbrowserBackend",
    "build_browser_diagnostics",
    "build_dashboard_url",
    "clear_browser_trace",
    "decide",
    "default_backend",
    "detect_browser_availability",
    "get_browser_metrics",
    "get_browser_trace",
    "get_default_backpressure_guard",
    "get_default_session_guard",
    "get_last_launch",
    "is_browser_trace_enabled",
    "launch_browser",
    "load_preferences",
    "record_browser_trace",
    "record_last_launch",
    "reset_browser_metrics",
    "reset_default_backpressure_guard",
    "reset_default_session_guard",
    "reset_last_launch",
    "resolve_policy",
    "set_browser_trace_enabled",
    "should_open_browser",
]
