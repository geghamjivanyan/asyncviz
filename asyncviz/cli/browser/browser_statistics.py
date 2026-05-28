"""Per-launch result object used by tests + the diagnostics endpoint.

Built once per :class:`BrowserLauncher` call. Holds the full reasoning
trail — policy + availability + readiness + process outcome — so the
CLI can render a single-line summary without re-querying the moving
parts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from asyncviz.cli.browser.browser_availability import BrowserAvailability
from asyncviz.cli.browser.browser_policy import PolicyDecision
from asyncviz.cli.browser.browser_process import ProcessLaunchOutcome
from asyncviz.cli.browser.browser_readiness import ProbeOutcome

LaunchStatus = Literal["opened", "skipped", "failed", "throttled", "deduped"]


@dataclass(frozen=True, slots=True)
class LaunchStatistics:
    """Composed view of one launch attempt."""

    status: LaunchStatus
    url: str
    policy: PolicyDecision
    availability: BrowserAvailability
    readiness: ProbeOutcome | None
    process: ProcessLaunchOutcome | None
    elapsed_seconds: float
    detail: str

    @property
    def opened(self) -> bool:
        return self.status == "opened"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "url": self.url,
            "elapsed_seconds": self.elapsed_seconds,
            "detail": self.detail,
            "policy": {
                "open": self.policy.open,
                "policy": str(self.policy.policy),
                "reason": self.policy.reason,
            },
            "availability": {
                "available": self.availability.available,
                "code": self.availability.code,
                "reason": self.availability.reason,
                "signals": list(self.availability.signals),
            },
            "readiness": asdict(self.readiness) if self.readiness else None,
            "process": asdict(self.process) if self.process else None,
        }
