"""Environment-variable + config preference resolution for the browser
launcher.

The user picks a default via ``--browser`` on the command line; env
vars layer on top so CI pipelines + shared shell profiles can flip
the default without rewriting every invocation. This module is the
single place that knows about every env var the browser layer reads.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from asyncviz.cli.browser.browser_policy import BrowserLaunchPolicy

#: Set to a truthy value to suppress every browser open. The detector
#: also honours this; we copy it into the policy layer so even
#: ``--browser always`` respects the operator's explicit opt-out.
ENV_NO_BROWSER = "ASYNCVIZ_NO_BROWSER"

#: ``ASYNCVIZ_BROWSER`` overrides the default policy when set
#: ("auto" / "always" / "never"). Useful in dotenv files.
ENV_BROWSER_POLICY = "ASYNCVIZ_BROWSER"


_TRUTHY = frozenset({"1", "true", "yes", "on", "y", "t"})


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in _TRUTHY


@dataclass(frozen=True, slots=True)
class BrowserPreferences:
    """Resolved environment-derived preference summary.

    ``policy`` is the env-overridden tri-state; ``hard_off`` is the
    "even ALWAYS should respect this" opt-out. The launcher folds both
    into the final decision.
    """

    policy: BrowserLaunchPolicy | None
    hard_off: bool


def load_preferences(environ: Mapping[str, str] | None = None) -> BrowserPreferences:
    """Read browser-related env vars.

    Returns ``policy=None`` when the env doesn't set a preference; the
    CLI's ``--browser`` default then wins.
    """
    env = environ if environ is not None else os.environ

    raw_policy = env.get(ENV_BROWSER_POLICY)
    policy: BrowserLaunchPolicy | None
    if raw_policy:
        try:
            policy = BrowserLaunchPolicy(raw_policy.lower())
        except ValueError:
            policy = None
    else:
        policy = None

    return BrowserPreferences(
        policy=policy,
        hard_off=_truthy(env.get(ENV_NO_BROWSER)),
    )
