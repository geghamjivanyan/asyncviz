"""Tri-state browser-launch policy.

The CLI exposes ``--browser auto|always|never``. The policy module
turns that knob + the runtime detection into a single boolean
decision. Separating the policy from the detector keeps the two
testable independently — a fake :class:`BrowserAvailability` is enough
to exercise every branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from asyncviz.cli.browser.browser_availability import BrowserAvailability


class BrowserLaunchPolicy(StrEnum):
    """User-supplied preference."""

    AUTO = "auto"
    """Open only when the environment looks interactive."""

    ALWAYS = "always"
    """Force open, even when detection would have skipped."""

    NEVER = "never"
    """Never open, even when the environment is interactive."""


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Result of resolving a policy + availability into a verdict."""

    open: bool
    policy: BrowserLaunchPolicy
    availability: BrowserAvailability
    reason: str

    @property
    def skipped(self) -> bool:
        return not self.open


def resolve_policy(
    raw: str | BrowserLaunchPolicy,
) -> BrowserLaunchPolicy:
    """Coerce a string or enum value into a :class:`BrowserLaunchPolicy`."""
    if isinstance(raw, BrowserLaunchPolicy):
        return raw
    if isinstance(raw, str):
        try:
            return BrowserLaunchPolicy(raw.lower())
        except ValueError as exc:
            raise ValueError(
                f"invalid browser policy {raw!r}: expected auto/always/never",
            ) from exc
    raise TypeError(f"expected str or BrowserLaunchPolicy, got {type(raw).__name__}")


def decide(
    policy: BrowserLaunchPolicy | Literal["auto", "always", "never"],
    availability: BrowserAvailability,
) -> PolicyDecision:
    """Resolve ``policy`` + ``availability`` into an explicit decision.

    Resolution rules:

    * ``ALWAYS`` — always open. The detector's verdict is recorded for
      diagnostics but doesn't gate the open.
    * ``NEVER`` — never open. The detector's verdict is recorded for
      diagnostics.
    * ``AUTO`` — open iff ``availability.available``.

    Returning a structured :class:`PolicyDecision` keeps the
    explanation alongside the boolean so the CLI can print "skipped
    (CI detected)" without re-running the detector.
    """
    resolved = resolve_policy(policy)
    if resolved is BrowserLaunchPolicy.ALWAYS:
        return PolicyDecision(
            open=True,
            policy=resolved,
            availability=availability,
            reason=f"forced open by policy=always (detector said {availability.code})",
        )
    if resolved is BrowserLaunchPolicy.NEVER:
        return PolicyDecision(
            open=False,
            policy=resolved,
            availability=availability,
            reason="skipped: policy=never",
        )
    # AUTO
    if availability.available:
        return PolicyDecision(
            open=True,
            policy=resolved,
            availability=availability,
            reason=f"auto-open: {availability.reason}",
        )
    return PolicyDecision(
        open=False,
        policy=resolved,
        availability=availability,
        reason=f"skipped: {availability.reason}",
    )
