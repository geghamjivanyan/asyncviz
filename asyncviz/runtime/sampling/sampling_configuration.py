"""Event-sampler configuration.

Centralizes every knob the sampling layer cares about: priority
overrides, per-priority retention thresholds, adaptive parameters,
budget windows, behavior flags.

Defaults are tuned for general-purpose runtimes — long-running
deployments under heavy load override via :func:`relaxed_config`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

SamplingMode = Literal["off", "fixed", "adaptive"]
"""Sampling regime.

* ``off`` — every event retained; the sampler is a pass-through.
* ``fixed`` — apply the static priority retention rates.
* ``adaptive`` (default) — let the adaptive controller tighten or
  relax thresholds based on observed pressure.
"""

DEFAULT_BUDGET_WINDOW_NS: Final[int] = 1_000_000_000  # 1 second
DEFAULT_BUDGET_TARGET_EVENTS: Final[int] = 50_000
"""Default soft cap on retained events per window."""

DEFAULT_OVERLOAD_RATIO: Final[float] = 1.5
"""When observed rate exceeds ``target_events * overload_ratio``,
the adaptive controller switches to ``overload`` mode."""


@dataclass(frozen=True, slots=True)
class SamplingConfig:
    """Immutable sampling configuration."""

    mode: SamplingMode = "adaptive"

    # ── per-priority retention thresholds ─────────────────────────
    critical_retention: float = 1.0
    """Always retained; non-1.0 values are clamped to 1.0 to preserve
    correctness for warnings/errors."""

    structural_retention: float = 1.0
    """Default 100% — structural events (task created/completed,
    queue created, etc.) preserve the topology graph."""

    state_retention: float = 0.5
    """Sampling rate for state/metric events under normal load."""

    delta_retention: float = 0.1
    """Aggressive sampling for repetitive deltas."""

    # ── adaptive parameters ───────────────────────────────────────
    budget_window_ns: int = DEFAULT_BUDGET_WINDOW_NS
    budget_target_events: int = DEFAULT_BUDGET_TARGET_EVENTS
    overload_ratio: float = DEFAULT_OVERLOAD_RATIO

    overload_floor: float = 0.05
    """Under overload, no priority drops below this retention rate
    (except where critical_retention promises otherwise)."""

    relax_decay: float = 0.9
    """Per-window decay applied to the observed rate when computing
    smoothed pressure — closer to 1.0 means slower adaptation."""

    # ── replay integration ────────────────────────────────────────
    emit_replay_markers: bool = True
    """When True, the sampler emits a sampling-marker event when a
    drop window closes, so replay reconstruction can render an
    explicit gap."""

    marker_window_events: int = 256
    """One marker per N events dropped (or at window close)."""

    # ── safety flags ──────────────────────────────────────────────
    never_drop_event_types: tuple[str, ...] = ()
    """Caller-supplied promise: these event_type strings are always
    retained, regardless of priority/budget."""

    deterministic_seed: int = 0xA5_BE_F7
    """Seed used by the deterministic-hash path so ``random``-style
    decisions are reproducible across runs."""

    extras: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for rate, name in (
            (self.critical_retention, "critical_retention"),
            (self.structural_retention, "structural_retention"),
            (self.state_retention, "state_retention"),
            (self.delta_retention, "delta_retention"),
            (self.overload_floor, "overload_floor"),
        ):
            if not (0.0 <= rate <= 1.0):
                raise ValueError(f"{name} must be in [0, 1] (got {rate})")
        if self.budget_window_ns < 1_000_000:
            raise ValueError("budget_window_ns must be >= 1ms")
        if self.budget_target_events < 1:
            raise ValueError("budget_target_events must be >= 1")
        if not (1.0 < self.overload_ratio < 100.0):
            raise ValueError("overload_ratio must be in (1, 100)")
        if not (0.0 < self.relax_decay < 1.0):
            raise ValueError("relax_decay must be in (0, 1)")
        if self.marker_window_events < 1:
            raise ValueError("marker_window_events must be >= 1")


def default_config() -> SamplingConfig:
    return SamplingConfig()


def off_config() -> SamplingConfig:
    """Pass-through — disables sampling entirely."""
    return SamplingConfig(mode="off")


def aggressive_config() -> SamplingConfig:
    """Heavy sampling for overloaded deployments."""
    return SamplingConfig(
        state_retention=0.2,
        delta_retention=0.02,
        budget_target_events=10_000,
        overload_floor=0.01,
    )


def relaxed_config() -> SamplingConfig:
    """Larger budget for production sessions that can afford to
    keep more events around."""
    return SamplingConfig(
        state_retention=0.75,
        delta_retention=0.25,
        budget_target_events=500_000,
        overload_floor=0.1,
    )
