"""Profile factory — derive a :class:`SpeedProfile` from a config."""

from __future__ import annotations

from asyncviz.replay.runtime.speed.models.speed_profile import (
    SpeedProfile,
    build_speed_profile,
)
from asyncviz.replay.runtime.speed.replay_speed_configuration import (
    ReplaySpeedConfig,
)


def profile_from_config(config: ReplaySpeedConfig) -> SpeedProfile:
    return build_speed_profile(
        presets=config.presets,
        min_speed=config.min_speed,
        max_speed=config.max_speed,
        default_speed=config.default_speed,
    )
