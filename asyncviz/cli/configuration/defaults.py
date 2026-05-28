"""Default values used by the CLI configuration layer.

Kept in one module so a change here (e.g. switching the default port)
ripples through the parser, the validation, and the docs without
hunting through call sites.
"""

from __future__ import annotations

from typing import Literal

#: Default dashboard host. Bound to loopback so the runtime never
#: accidentally listens publicly. Operators flip this with
#: ``--host 0.0.0.0`` or ``ASYNCVIZ_HOST``.
DEFAULT_DASHBOARD_HOST: str = "127.0.0.1"

#: Default dashboard port — same as the bootstrap default so the CLI
#: and ``asyncviz.start()`` stay aligned.
DEFAULT_DASHBOARD_PORT: int = 8877

#: How long to wait for the embedded uvicorn server to start before
#: declaring the dashboard unhealthy.
DEFAULT_STARTUP_TIMEOUT_SECONDS: float = 5.0

#: How long to wait for the user's subprocess to terminate after the
#: CLI sends SIGTERM. Tuned for a graceful flush of any final events
#: without lingering forever.
DEFAULT_SUBPROCESS_SHUTDOWN_TIMEOUT_SECONDS: float = 5.0

#: Browser open default. ``"auto"`` opens when a display is detected,
#: ``"never"`` skips, ``"always"`` forces.
DEFAULT_BROWSER_PREFERENCE: Literal["auto", "always", "never"] = "auto"
