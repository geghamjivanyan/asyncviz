"""Mutable loop-state snapshot.

Distinct from :class:`LoopCapabilities` (a one-time probe) — this
records *current* runtime state: whether the manager has actually
installed uvloop, the timestamp of the last detection pass, the
number of fallback activations recorded.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.compat.models.loop_capabilities import LoopCapabilities
from asyncviz.runtime.compat.models.loop_kind import LoopKind


@dataclass(frozen=True, slots=True)
class LoopState:
    """Frozen snapshot of the manager's runtime state."""

    active_kind: LoopKind
    capabilities: LoopCapabilities
    installed_uvloop: bool
    install_attempted: bool
    install_error: str
    """Empty string when no install error has been recorded."""

    fallback_activations: int
    """How many times the manager observed a feature it expected but
    that the active loop refused to expose. Each activation routes
    through the documented asyncio fallback path."""

    drift_warnings: int
    """How many times monotonic vs ``loop.time()`` drifted beyond
    the configured tolerance."""

    detected_at_ns: int
