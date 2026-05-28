"""Browser auto-open runtime options.

Translates the existing CLI tri-state + env preferences into a
strongly-typed option struct. The runtime launcher reads this and
turns it into a :class:`asyncviz.cli.browser.BrowserLaunchConfig` at
mount time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from asyncviz.configuration.runtime_defaults import (
    DEFAULT_BROWSER_POLICY,
    DEFAULT_READINESS_INTERVAL_SECONDS,
    DEFAULT_READINESS_TIMEOUT_SECONDS,
)

BrowserPolicy = Literal["auto", "always", "never"]


@dataclass(frozen=True, slots=True)
class BrowserOptions:
    """Configuration for the dashboard auto-open behaviour."""

    policy: BrowserPolicy = DEFAULT_BROWSER_POLICY
    readiness_timeout_seconds: float = DEFAULT_READINESS_TIMEOUT_SECONDS
    readiness_interval_seconds: float = DEFAULT_READINESS_INTERVAL_SECONDS
    session_id: str | None = None
    """Optional open-once dedup key (typically the runtime id)."""

    @property
    def should_attempt(self) -> bool:
        """``True`` when the policy permits an attempt (auto / always)."""
        return self.policy != "never"
