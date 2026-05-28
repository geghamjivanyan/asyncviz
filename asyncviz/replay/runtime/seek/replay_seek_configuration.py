"""Replay seek orchestration configuration.

This sits *above* the loader's :class:`ReplaySeekRuntime` (which
does the actual checkpoint + delta-replay work) and adds the
production concerns the lower layer doesn't address: coalescing
rapid scrubs, caching reconstructed states, pausing the engine
before reconstruction, awaitable barriers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

SeekTargetKind = Literal["sequence", "timestamp", "marker", "relative"]
"""How the caller expresses a seek target."""

SeekStrategy = Literal["best_effort", "exact_only"]
"""``best_effort`` (default) lands on the *first* frame ``>= target``.
``exact_only`` rejects seeks that don't land precisely on the target
sequence — used by debugger-style integrations where overshoot is
unacceptable."""

DEFAULT_SEEK_CACHE_CAPACITY: Final[int] = 16
"""LRU capacity for reconstructed-state cache. Each entry retains
one :class:`VirtualRuntimeState` — bounded memory matters more
than coverage."""

DEFAULT_SEEK_QUEUE_CAPACITY: Final[int] = 32
DEFAULT_RECONSTRUCTION_BUDGET_MS: Final[float] = 250.0
DEFAULT_SEEK_TIMEOUT_SECONDS: Final[float] = 5.0


@dataclass(frozen=True, slots=True)
class ReplaySeekConfig:
    """Immutable seek-coordination configuration."""

    cache_capacity: int = DEFAULT_SEEK_CACHE_CAPACITY
    """Soft cap on the reconstruction LRU."""

    queue_capacity: int = DEFAULT_SEEK_QUEUE_CAPACITY
    """Bounded request queue — scrub bursts collapse via
    drop-oldest."""

    reconstruction_budget_ms: float = DEFAULT_RECONSTRUCTION_BUDGET_MS
    """Soft budget for one reconstruction. Exceeding it bumps a
    diagnostic counter; doesn't abort."""

    seek_timeout_seconds: float = DEFAULT_SEEK_TIMEOUT_SECONDS

    strategy: SeekStrategy = "best_effort"

    coalesce_intermediate_scrubs: bool = True
    """When True, in-flight seek requests are cancelled by newer
    ones — the default for UI scrubbing where intermediate targets
    are noise."""

    pause_before_seek: bool = True
    """When True, the coordinator transitions the engine to
    ``PAUSED`` before reconstruction starts + restores the previous
    playback phase on completion. When False, the engine keeps
    running while reconstruction happens in parallel — used by
    background replay tooling that doesn't surface UI."""

    resume_after_seek: bool = True
    """Restore the playback phase that existed before the seek
    started. Ignored when ``pause_before_seek=False``."""

    record_checkpoint_on_seek: bool = True
    """When True, the reconstructed state is recorded as a new
    checkpoint so subsequent seeks to the same sequence are O(0)."""

    verify_integrity_on_seek: bool = False
    """When True, the coordinator verifies that the reconstructed
    state's ``last_sequence`` matches the seek target. Off by
    default — adds a per-seek hash check."""

    def __post_init__(self) -> None:
        if self.cache_capacity < 0:
            raise ValueError("cache_capacity must be >= 0")
        if self.queue_capacity < 1:
            raise ValueError("queue_capacity must be >= 1")
        if self.reconstruction_budget_ms < 0:
            raise ValueError("reconstruction_budget_ms must be >= 0")
        if self.seek_timeout_seconds < 0:
            raise ValueError("seek_timeout_seconds must be >= 0")
