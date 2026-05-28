"""Typed configuration for one browser-launch attempt.

The CLI's :class:`RunCliConfig` carries scalar knobs (`--browser`,
`--port`, …). This module turns them into a focused
:class:`BrowserLaunchConfig` that the launcher consumes without
needing to know about the wider CLI config shape.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.cli.browser.browser_policy import BrowserLaunchPolicy

#: Default seconds to wait for the dashboard to respond before opening.
DEFAULT_READINESS_TIMEOUT_SECONDS: float = 5.0

#: Default seconds between readiness probes.
DEFAULT_READINESS_INTERVAL_SECONDS: float = 0.1

#: Default seconds before we abandon the browser-open thread.
DEFAULT_LAUNCH_TIMEOUT_SECONDS: float = 5.0

#: Default initial delay before issuing ``webbrowser.open`` — gives
#: uvicorn a beat to settle. The readiness probe is the canonical
#: gate now; this delay is a safety net for transports without a
#: probe URL.
DEFAULT_LAUNCH_DELAY_SECONDS: float = 0.2


@dataclass(frozen=True, slots=True)
class BrowserLaunchConfig:
    """Inputs the launcher needs to make one open attempt."""

    url: str
    """The dashboard URL to open. The launcher does not re-derive it."""

    policy: BrowserLaunchPolicy = BrowserLaunchPolicy.AUTO
    """User-facing tri-state preference."""

    readiness_url: str | None = None
    """Optional probe URL (usually ``{base}/api/health/live``).
    ``None`` skips the probe — the launcher opens after the static
    delay."""

    readiness_timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS
    """Max wait for the readiness probe before opening anyway."""

    readiness_interval_seconds: float = DEFAULT_READINESS_INTERVAL_SECONDS
    """Sleep between probe attempts."""

    launch_timeout_seconds: float = DEFAULT_LAUNCH_TIMEOUT_SECONDS
    """Max wait for the actual ``webbrowser.open`` call."""

    launch_delay_seconds: float = DEFAULT_LAUNCH_DELAY_SECONDS
    """Static delay applied when no readiness probe is configured."""

    session_id: str | None = None
    """Optional dedup key — open at most once per session id. Useful
    when the same runtime is restarted in dev: pass the runtime id
    so a quick Ctrl-C + restart doesn't spawn two tabs."""
