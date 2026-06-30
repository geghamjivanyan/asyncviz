"""Speed profile — the (presets + limits) bundle the coordinator
exposes to callers.

A profile is a *normalized* view over :class:`ReplaySpeedConfig`'s
preset list — invalid entries dropped, sorted, deduplicated, with a
default-speed pointer. Components consume this when rendering the
preset selector.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SpeedProfile:
    """Normalized speed profile."""

    presets: tuple[float, ...] = field(default_factory=tuple)
    """Sorted, deduped, in-bounds presets."""

    min_speed: float = 0.05
    max_speed: float = 32.0
    default_speed: float = 1.0

    def index_of(self, speed: float) -> int:
        """Index of the *largest* preset ``<= speed``. ``-1`` when
        ``speed`` is below the lowest preset."""
        last = -1
        for i, preset in enumerate(self.presets):
            if preset <= speed:
                last = i
            else:
                break
        return last

    def next_preset(self, current: float) -> float:
        """The preset *strictly* greater than ``current`` — or the
        current value when already at max."""
        for preset in self.presets:
            if preset > current:
                return preset
        return self.presets[-1] if self.presets else current

    def previous_preset(self, current: float) -> float:
        """The preset *strictly* less than ``current`` — or the
        current value when already at min."""
        candidate = None
        for preset in self.presets:
            if preset < current:
                candidate = preset
            else:
                break
        return (
            candidate if candidate is not None else (self.presets[0] if self.presets else current)
        )


def build_speed_profile(
    *,
    presets: tuple[float, ...],
    min_speed: float,
    max_speed: float,
    default_speed: float,
) -> SpeedProfile:
    """Normalize raw config inputs into a :class:`SpeedProfile`."""
    cleaned = sorted({round(p, 6) for p in presets if p > 0 and min_speed <= p <= max_speed})
    return SpeedProfile(
        presets=tuple(cleaned),
        min_speed=min_speed,
        max_speed=max_speed,
        default_speed=default_speed,
    )
