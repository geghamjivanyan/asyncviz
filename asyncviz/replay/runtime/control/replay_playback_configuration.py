"""Configuration for the replay playback coordinator.

The coordinator sits above :class:`PauseController` /
:class:`PlaybackController` and owns the *transition* concerns those
primitives don't address by themselves — pause-after-sequence
scheduling, awaitable barriers, race-condition isolation, etc.

Keep construction cheap so tests can build many configs without
paying for option-parsing churn."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

PauseTrigger = Literal[
    "immediate",
    "after_current_frame",
    "at_sequence",
    "at_timestamp",
]
"""When a pause request should take effect.

``immediate`` — the coordinator pauses on the next coordination tick
(may race with a half-applied frame; reducer-safe regardless).

``after_current_frame`` — the playback loop completes the in-flight
frame, then transitions to paused. Default for ergonomic pauses
because it never leaves the reducer mid-state.

``at_sequence`` — the coordinator arms a *gate* that fires when the
playback loop reaches ``target_sequence``. Used by breakpoint-style
replay debugging.

``at_timestamp`` — same as ``at_sequence`` but expressed in
``monotonic_ns``."""

DEFAULT_PAUSE_LATENCY_BUDGET_NS: Final[int] = 50_000_000  # 50 ms
DEFAULT_COORDINATION_QUEUE_CAPACITY: Final[int] = 64
DEFAULT_TRANSITION_TIMEOUT_SECONDS: Final[float] = 5.0


@dataclass(frozen=True, slots=True)
class ReplayPlaybackCoordinationConfig:
    """Immutable coordinator configuration."""

    default_pause_trigger: PauseTrigger = "after_current_frame"
    """Trigger applied when a caller doesn't specify one."""

    pause_latency_budget_ns: int = DEFAULT_PAUSE_LATENCY_BUDGET_NS
    """Soft cap on the time between a pause request being received
    and the engine actually reaching the paused state. Exceeding it
    bumps the ``pause_budget_exceeded`` metric — informational, not
    fatal."""

    coordination_queue_capacity: int = DEFAULT_COORDINATION_QUEUE_CAPACITY
    """Bounded inbound queue for pause/resume/step requests. Hitting
    this trips a backpressure event + the oldest pending request is
    dropped (drop-oldest)."""

    transition_timeout_seconds: float = DEFAULT_TRANSITION_TIMEOUT_SECONDS
    """Default timeout for ``await_paused`` / ``await_resumed`` —
    callers can override per-call."""

    strict_transitions: bool = True
    """When True, illegal transitions (resume while not paused, etc.)
    raise; otherwise they're counted + ignored."""

    coalesce_repeated_requests: bool = True
    """When True, redundant pause/resume requests collapse into a
    single coordination event — avoids transition churn under
    rapid-fire UI input."""

    def __post_init__(self) -> None:
        if self.coordination_queue_capacity < 1:
            raise ValueError("coordination_queue_capacity must be >= 1")
        if self.pause_latency_budget_ns < 0:
            raise ValueError("pause_latency_budget_ns must be >= 0")
        if self.transition_timeout_seconds < 0:
            raise ValueError("transition_timeout_seconds must be >= 0")
