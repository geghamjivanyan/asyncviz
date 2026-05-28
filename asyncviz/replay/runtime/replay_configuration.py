"""Replay runtime engine configuration.

One immutable dataclass that controls how the engine plays a
recording: clock source, default playback speed, dispatch queue
size, checkpoint cadence, websocket integration toggles.

Most consumers construct one with defaults — only specialized tests
and tooling override anything beyond ``initial_speed``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

ClockSource = Literal["monotonic", "manual"]
"""``monotonic`` (default) — engine uses :func:`time.monotonic_ns`.
``manual`` — engine takes ticks from outside (tests, simulators)."""

PlaybackMode = Literal["realtime", "as_fast_as_possible", "step"]
"""``realtime`` — honor frame timestamps + playback speed.
``as_fast_as_possible`` — dispatch frames back-to-back without
deferring on the clock (useful for bulk catch-up).
``step`` — dispatch one frame per explicit step call."""

DEFAULT_MAX_DISPATCH_QUEUE: Final[int] = 4096
DEFAULT_CHECKPOINT_INTERVAL_FRAMES: Final[int] = 256


@dataclass(frozen=True, slots=True)
class ReplayEngineConfig:
    """Immutable engine configuration."""

    initial_speed: float = 1.0
    """``1.0`` is realtime; ``2.0`` is 2x speed; ``0.25`` is quarter
    speed. Non-positive values are rejected at construction; reverse
    playback is reserved for a future mode."""

    playback_mode: PlaybackMode = "realtime"

    clock_source: ClockSource = "monotonic"

    max_dispatch_queue: int = DEFAULT_MAX_DISPATCH_QUEUE
    """Soft cap on the outbound dispatch queue (websocket bridge +
    listeners). Overflow trips a backpressure event + falls back to
    blocking the engine loop until the queue drains."""

    checkpoint_interval_frames: int = DEFAULT_CHECKPOINT_INTERVAL_FRAMES
    """How often the runtime takes its own state checkpoints so a
    future seek can resume without re-reducing from scratch."""

    catch_up_threshold_seconds: float = 0.5
    """If the engine falls more than this many seconds behind virtual
    time, it stops sleeping and dispatches back-to-back until caught
    up. Prevents drift from cascading."""

    enforce_strict_ordering: bool = True
    """When True, the engine rejects any frame whose ``sequence`` is
    not strictly after the cursor's ``last_sequence``."""

    websocket_enabled: bool = True
    """Whether to attach the websocket bridge by default. Tests
    often disable this to isolate engine logic."""

    def __post_init__(self) -> None:
        if self.initial_speed <= 0:
            raise ValueError(
                f"initial_speed must be > 0 (got {self.initial_speed})",
            )
        if self.max_dispatch_queue < 1:
            raise ValueError("max_dispatch_queue must be >= 1")
        if self.checkpoint_interval_frames < 1:
            raise ValueError("checkpoint_interval_frames must be >= 1")
