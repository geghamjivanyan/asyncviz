"""Preset cycling — wraps :class:`SpeedProfile` for ``increase``/
``decrease`` callers."""

from __future__ import annotations

from asyncviz.replay.runtime.speed.models.speed_profile import SpeedProfile


def next_preset(profile: SpeedProfile, current: float) -> float:
    return profile.next_preset(current)


def previous_preset(profile: SpeedProfile, current: float) -> float:
    return profile.previous_preset(current)


def nearest_preset(profile: SpeedProfile, current: float) -> float:
    """Return the preset closest to ``current`` (ties go to the
    smaller value). Useful for "snap to preset" UX after a freehand
    speed slider."""
    if not profile.presets:
        return current
    best = profile.presets[0]
    best_distance = abs(best - current)
    for preset in profile.presets[1:]:
        distance = abs(preset - current)
        if distance < best_distance:
            best = preset
            best_distance = distance
    return best


def restore_default(profile: SpeedProfile) -> float:
    return profile.default_speed
