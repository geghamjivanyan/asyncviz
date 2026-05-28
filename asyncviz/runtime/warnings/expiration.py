"""Active-warning expiration policy.

If a warning hasn't been re-observed for ``ttl_seconds`` (monotonic), the
manager treats it as auto-resolved and moves it to the resolved bucket.
Prevents runaway long-lived warnings from filling the active list when
their underlying condition cleared without a deliberate resolution.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.warnings.lifecycle import WarningLifecycle

#: Default expiration window — long enough that real warnings persist for
#: an operator's whole session, short enough that stale chatter clears.
DEFAULT_TTL_SECONDS: float = 60.0


@dataclass(frozen=True, slots=True)
class ExpirationPolicy:
    """Configurable knobs for when a warning auto-resolves."""

    ttl_seconds: float = DEFAULT_TTL_SECONDS

    def is_expired(
        self,
        lifecycle: WarningLifecycle,
        *,
        now_monotonic_ns: int,
    ) -> bool:
        if lifecycle.resolved:
            return False  # already terminal; nothing to expire
        elapsed_ns = now_monotonic_ns - lifecycle.last_observed_monotonic_ns
        return elapsed_ns >= int(self.ttl_seconds * 1_000_000_000)
