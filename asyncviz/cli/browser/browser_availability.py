"""Typed result for browser-environment detection.

Lives in its own module so consumers can ``isinstance`` / pattern-match
on the result without dragging in the detection logic. The detector
returns this object; the policy layer consumes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

#: Tagged reason codes — kept stable so callers can switch on them
#: without parsing free-form ``reason`` strings.
AvailabilityCode = Literal[
    "available",
    "no-tty",
    "ci",
    "explicit-opt-out",
    "ssh-no-display",
    "no-display",
    "no-browser-registered",
    "unknown",
]


@dataclass(frozen=True, slots=True)
class BrowserAvailability:
    """Detection result + the reasoning behind it.

    ``available`` is the boolean the policy layer cares about;
    ``code`` is a stable machine-readable tag; ``reason`` is a short
    human string for logs/diagnostics; ``signals`` records every env
    var / heuristic that contributed so the doctor command can
    explain *why*.
    """

    available: bool
    code: AvailabilityCode
    reason: str
    signals: tuple[str, ...] = field(default_factory=tuple)

    def with_signal(self, signal: str) -> BrowserAvailability:
        """Return a copy with ``signal`` appended to the trail."""
        return BrowserAvailability(
            available=self.available,
            code=self.code,
            reason=self.reason,
            signals=(*self.signals, signal),
        )
