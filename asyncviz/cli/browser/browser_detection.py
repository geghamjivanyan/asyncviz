"""Browser-environment detection.

Probes the process environment to decide whether opening a browser
will produce a useful UX. The detector deliberately errs on the side
of "don't surprise the operator with a popup" — CI, headless SSH,
and no-DISPLAY Linux all skip by default. Operators override via
``--browser always`` or ``ASYNCVIZ_BROWSER=always``.

The detector returns a :class:`BrowserAvailability` (defined in
:mod:`browser_availability`); the policy layer turns that into the
final decision. The split keeps each module unit-testable in
isolation.
"""

from __future__ import annotations

import os
import platform
import sys
import webbrowser
from collections.abc import Mapping

from asyncviz.cli.browser.browser_availability import BrowserAvailability
from asyncviz.cli.browser.browser_policy import BrowserLaunchPolicy
from asyncviz.cli.browser.browser_preferences import (
    ENV_NO_BROWSER,
    load_preferences,
)

#: Backwards-compatible alias for callers that import the old name.
BrowserPreference = BrowserLaunchPolicy


def detect_browser_availability(
    environ: Mapping[str, str] | None = None,
) -> BrowserAvailability:
    """Best-effort guess at whether opening a browser will work.

    ``environ`` is injectable for tests; production callers pass
    ``None`` to read the live process environment.
    """
    env = environ if environ is not None else os.environ

    # Explicit opt-outs trump everything.
    prefs = load_preferences(env)
    if prefs.hard_off:
        return BrowserAvailability(
            available=False,
            code="explicit-opt-out",
            reason=f"{ENV_NO_BROWSER} set",
            signals=(ENV_NO_BROWSER,),
        )
    if prefs.policy is BrowserLaunchPolicy.NEVER:
        return BrowserAvailability(
            available=False,
            code="explicit-opt-out",
            reason="ASYNCVIZ_BROWSER=never",
            signals=("ASYNCVIZ_BROWSER",),
        )

    # CI signals — almost always headless.
    for key in ("CI", "GITHUB_ACTIONS", "BUILDKITE", "GITLAB_CI", "CIRCLECI"):
        if env.get(key):
            return BrowserAvailability(
                available=False,
                code="ci",
                reason=f"CI environment detected via {key}",
                signals=(key,),
            )

    # SSH without forwarding usually has no display (macOS is the
    # exception — SSH'd Macs can still launch ``open``).
    if env.get("SSH_CONNECTION") and not env.get("DISPLAY") and platform.system() != "Darwin":
        return BrowserAvailability(
            available=False,
            code="ssh-no-display",
            reason="SSH session without DISPLAY",
            signals=("SSH_CONNECTION",),
        )

    # No DISPLAY on Linux is a strong "headless" signal.
    if platform.system() == "Linux" and not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
        return BrowserAvailability(
            available=False,
            code="no-display",
            reason="no DISPLAY/WAYLAND_DISPLAY on Linux",
            signals=("DISPLAY", "WAYLAND_DISPLAY"),
        )

    # webbrowser.get() raises when nothing is registered.
    try:
        webbrowser.get()
    except webbrowser.Error as exc:
        return BrowserAvailability(
            available=False,
            code="no-browser-registered",
            reason=f"no registered browser: {exc}",
        )

    # When stdout/stderr aren't TTYs we're probably scripted; still let
    # the launcher try, but flag the signal so doctor can report it.
    if not (sys.stdout.isatty() or sys.stderr.isatty()):
        return BrowserAvailability(
            available=True,
            code="available",
            reason="no TTY but browser registered (best-effort)",
            signals=("no-tty",),
        )

    return BrowserAvailability(
        available=True,
        code="available",
        reason="browser available",
    )


def should_open_browser(
    preference,  # type: ignore[no-untyped-def]
    availability: BrowserAvailability | None = None,
) -> bool:
    """Backwards-compatible boolean resolver.

    Delegates to :func:`asyncviz.cli.browser.browser_policy.decide`
    so the policy logic stays in one place. Kept here so
    pre-refactor callers (existing tests, the legacy launcher) keep
    working.
    """
    from asyncviz.cli.browser.browser_policy import decide

    avail = availability if availability is not None else detect_browser_availability()
    return decide(preference, avail).open
