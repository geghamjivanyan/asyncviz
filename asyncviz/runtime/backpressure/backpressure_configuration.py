"""Event-backpressure configuration.

Centralizes every knob the overload-protection layer cares about:
state-machine hysteresis bands, per-domain queue capacities,
emergency-mode triggers, replay-overflow behavior.

Defaults are tuned for a production runtime — overloaded clusters
override via :func:`relaxed_config`, embedded deployments via
:func:`lean_config`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

DropPolicy = Literal["drop-oldest", "drop-newest", "drop-low-priority", "block"]
"""How a bounded channel handles overflow."""

EmergencyAction = Literal["shed", "disconnect", "halt"]
"""What the emergency-mode entry triggers downstream.

* ``shed`` — keep running but apply the aggressive sampling tier.
* ``disconnect`` — terminate misbehaving subscribers.
* ``halt`` — refuse new events until pressure drops.
"""

DEFAULT_CHANNEL_CAPACITY: Final[int] = 16_384
DEFAULT_WEBSOCKET_CAPACITY: Final[int] = 8_192
DEFAULT_RECORDER_CAPACITY: Final[int] = 32_768
DEFAULT_REDUCER_CAPACITY: Final[int] = 4_096

DEFAULT_ELEVATED_THRESHOLD: Final[float] = 0.50
DEFAULT_OVERLOAD_THRESHOLD: Final[float] = 0.80
DEFAULT_EMERGENCY_THRESHOLD: Final[float] = 0.95

DEFAULT_DEGRADE_DECAY: Final[float] = 0.9
"""EMA decay for the pressure signal — closer to 1.0 is slower."""

DEFAULT_RECOVERY_HOLD_NS: Final[int] = 1_000_000_000  # 1 second
"""How long the state must remain "below threshold" before a
downgrade is committed (anti-flap dwell time)."""


@dataclass(frozen=True, slots=True)
class BackpressureConfig:
    """Immutable backpressure-controller configuration."""

    # ── channel capacities ────────────────────────────────────────
    bus_capacity: int = DEFAULT_CHANNEL_CAPACITY
    websocket_capacity: int = DEFAULT_WEBSOCKET_CAPACITY
    recorder_capacity: int = DEFAULT_RECORDER_CAPACITY
    reducer_capacity: int = DEFAULT_REDUCER_CAPACITY

    # ── default drop policy per channel kind ──────────────────────
    bus_drop_policy: DropPolicy = "drop-low-priority"
    websocket_drop_policy: DropPolicy = "drop-oldest"
    recorder_drop_policy: DropPolicy = "block"
    """Recorder defaults to ``block`` because we'd rather slow the
    producer than drop persisted events. Operators with a fast disk
    can switch to drop-oldest for lower-latency."""

    reducer_drop_policy: DropPolicy = "drop-low-priority"

    # ── state-machine bands (fraction of capacity) ────────────────
    elevated_threshold: float = DEFAULT_ELEVATED_THRESHOLD
    overload_threshold: float = DEFAULT_OVERLOAD_THRESHOLD
    emergency_threshold: float = DEFAULT_EMERGENCY_THRESHOLD
    """When the pressure signal crosses this fraction, the
    controller enters emergency mode + invokes ``emergency_action``."""

    # ── smoothing ─────────────────────────────────────────────────
    degrade_decay: float = DEFAULT_DEGRADE_DECAY
    recovery_hold_ns: int = DEFAULT_RECOVERY_HOLD_NS

    # ── emergency behavior ────────────────────────────────────────
    emergency_action: EmergencyAction = "shed"

    # ── recorder + replay ─────────────────────────────────────────
    emit_overflow_markers: bool = True
    """When True, the recorder embeds an explicit overflow-marker
    event into the recording stream so replay reconstruction can
    render gaps where events were dropped."""

    marker_summary_window: int = 1024

    # ── safety toggles ────────────────────────────────────────────
    enforce_priority_floor: bool = True
    """When True, structural + critical events bypass drop policies
    regardless of overload state. Disabling this trades correctness
    for raw throughput; do not set False in production."""

    extras: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for capacity, name in (
            (self.bus_capacity, "bus_capacity"),
            (self.websocket_capacity, "websocket_capacity"),
            (self.recorder_capacity, "recorder_capacity"),
            (self.reducer_capacity, "reducer_capacity"),
        ):
            if capacity < 1:
                raise ValueError(f"{name} must be >= 1")
        for band, name in (
            (self.elevated_threshold, "elevated_threshold"),
            (self.overload_threshold, "overload_threshold"),
            (self.emergency_threshold, "emergency_threshold"),
        ):
            if not (0.0 < band <= 1.0):
                raise ValueError(f"{name} must be in (0, 1] (got {band})")
        if not (self.elevated_threshold < self.overload_threshold < self.emergency_threshold):
            raise ValueError(
                "thresholds must be strictly ordered elevated < overload < emergency",
            )
        if not (0.0 < self.degrade_decay < 1.0):
            raise ValueError("degrade_decay must be in (0, 1)")
        if self.recovery_hold_ns < 0:
            raise ValueError("recovery_hold_ns must be >= 0")
        if self.marker_summary_window < 1:
            raise ValueError("marker_summary_window must be >= 1")


def default_config() -> BackpressureConfig:
    return BackpressureConfig()


def lean_config() -> BackpressureConfig:
    """Smaller channels for embedded / memory-constrained
    deployments."""
    return BackpressureConfig(
        bus_capacity=2_048,
        websocket_capacity=1_024,
        recorder_capacity=4_096,
        reducer_capacity=512,
    )


def relaxed_config() -> BackpressureConfig:
    """Larger channels + later overload entry for high-throughput
    deployments."""
    return BackpressureConfig(
        bus_capacity=131_072,
        websocket_capacity=65_536,
        recorder_capacity=262_144,
        reducer_capacity=16_384,
        elevated_threshold=0.65,
        overload_threshold=0.85,
        emergency_threshold=0.98,
    )
