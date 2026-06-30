"""Speed-coordinator configuration.

The new coordinator sits *above* the existing
:class:`asyncviz.replay.runtime.replay_speed.SpeedController`
primitive — the primitive flips the clock's speed atomically; the
coordinator adds presets, limits, awaitable transitions, drift
tracking, and coalescing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

DEFAULT_PRESETS: Final[tuple[float, ...]] = (
    0.1,
    0.25,
    0.5,
    1.0,
    2.0,
    4.0,
    8.0,
    16.0,
)
"""Canonical speed presets. ``1.0`` must always be present (it's
treated as the "default" preset by :func:`SpeedController.restore_default`)."""

DEFAULT_MIN_SPEED: Final[float] = 0.05
DEFAULT_MAX_SPEED: Final[float] = 32.0
DEFAULT_QUEUE_CAPACITY: Final[int] = 16
DEFAULT_TRANSITION_TIMEOUT_SECONDS: Final[float] = 2.0
DEFAULT_DRIFT_SAMPLE_INTERVAL_NS: Final[int] = 100_000_000  # 100 ms

InvalidSpeedPolicy = Literal["clamp", "reject"]
"""How invalid (out-of-range, NaN, ≤0) speed requests are handled.

* ``clamp`` (default) — silently clamp to the allowed range.
* ``reject`` — surface a failed result instead of touching the clock.
"""


@dataclass(frozen=True, slots=True)
class ReplaySpeedConfig:
    """Immutable coordinator configuration."""

    default_speed: float = 1.0
    """Speed restored by :meth:`restore_default`. Must satisfy
    ``min_speed <= default_speed <= max_speed``."""

    min_speed: float = DEFAULT_MIN_SPEED
    max_speed: float = DEFAULT_MAX_SPEED

    presets: tuple[float, ...] = DEFAULT_PRESETS
    """Ordered speed levels for ``increase``/``decrease``.
    Validated at construction; presets outside ``[min, max]`` are
    silently dropped."""

    invalid_speed_policy: InvalidSpeedPolicy = "clamp"

    queue_capacity: int = DEFAULT_QUEUE_CAPACITY
    """Bounded queue for rapid speed changes (drop-oldest)."""

    coalesce_repeated_requests: bool = True
    """Collapse redundant same-speed requests into a single
    transition."""

    transition_timeout_seconds: float = DEFAULT_TRANSITION_TIMEOUT_SECONDS

    drift_sample_interval_ns: int = DEFAULT_DRIFT_SAMPLE_INTERVAL_NS
    """How often the coordinator samples virtual-time against
    expected progression for drift telemetry. ``0`` disables."""

    history_capacity: int = 32
    """Trailing ring of recent speed transitions for diagnostics."""

    listeners_isolated: bool = True
    """When True (default), listener exceptions are caught + logged
    rather than propagated."""

    extras: dict[str, str] = field(default_factory=dict)
    """Free-form annotation bag — ignored by the coordinator but
    available for downstream tooling."""

    def __post_init__(self) -> None:
        if self.min_speed <= 0:
            raise ValueError("min_speed must be > 0")
        if self.max_speed <= self.min_speed:
            raise ValueError("max_speed must be > min_speed")
        if not (self.min_speed <= self.default_speed <= self.max_speed):
            raise ValueError(
                f"default_speed {self.default_speed} outside [{self.min_speed}, {self.max_speed}]",
            )
        if self.queue_capacity < 1:
            raise ValueError("queue_capacity must be >= 1")
        if self.transition_timeout_seconds < 0:
            raise ValueError("transition_timeout_seconds must be >= 0")
        if self.drift_sample_interval_ns < 0:
            raise ValueError("drift_sample_interval_ns must be >= 0")
        if self.history_capacity < 1:
            raise ValueError("history_capacity must be >= 1")
