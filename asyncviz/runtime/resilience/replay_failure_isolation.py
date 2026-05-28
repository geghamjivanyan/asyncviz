"""Replay-subsystem failure isolation adapter.

Wraps the replay subsystem behind the resilience manager. The
adapter exposes:

* ``isolate_decode(payload_kind, ...)`` — sync boundary used by the
  decoder so corrupt frames are quarantined instead of crashing
  playback.
* ``isolate_session(...)`` — async boundary the session loop wraps.
* ``quarantined_frames()`` — operator-facing inventory of dropped
  payloads.

Replay is *deterministic-by-construction* — the boundary preserves
that by exposing an explicit ``payload_kind`` so identical replay
streams quarantine identical frames.
"""

from __future__ import annotations

from collections.abc import Iterable

from asyncviz.runtime.resilience.failure_domain import FailureDomain
from asyncviz.runtime.resilience.subsystem_boundary import (
    AsyncSubsystemBoundary,
    SubsystemBoundary,
)


class ReplayFailureIsolation:
    """Replay-specific helpers on top of the failure domain."""

    __slots__ = ("_domain",)

    def __init__(self, domain: FailureDomain) -> None:
        self._domain = domain

    def isolate_decode(
        self,
        *,
        payload_kind: str,
        suppress: bool = True,
    ) -> SubsystemBoundary:
        """Sync boundary for a single decode call.

        Swallows :class:`SubsystemUnavailable` so the body skip
        when the breaker is open is silent — corruption errors
        still propagate (they're in :data:`DO_NOT_RETRY`)."""
        return SubsystemBoundary(
            self._domain,
            payload_kind=payload_kind,
            suppress=suppress,
            on_failure=None,
            swallow_unavailable=True,
        )

    def isolate_session(
        self,
        *,
        suppress: bool = False,
    ) -> AsyncSubsystemBoundary:
        """Async boundary for the session loop. Session-level
        failures must surface so the loop exits cleanly."""
        return AsyncSubsystemBoundary(
            self._domain,
            payload_kind="",
            suppress=suppress,
            on_failure=None,
            swallow_unavailable=False,
        )

    def quarantined_frames(self) -> tuple[str, ...]:
        return self._domain.quarantined()

    def release_quarantine(self, payload_kind: str) -> bool:
        return self._domain.release_quarantine(payload_kind)

    def bulk_release(self, payload_kinds: Iterable[str]) -> int:
        released = 0
        for kind in payload_kinds:
            if self._domain.release_quarantine(kind):
                released += 1
        return released
