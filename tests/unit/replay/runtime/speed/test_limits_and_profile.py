"""Limit + profile tests."""

from __future__ import annotations

import math

from asyncviz.replay.runtime.speed import (
    build_speed_profile,
    clamp_speed,
    nearest_preset,
    next_preset,
    previous_preset,
)


def test_clamp_accepts_in_range() -> None:
    verdict = clamp_speed(2.0, min_speed=0.1, max_speed=16.0)
    assert verdict.accepted
    assert not verdict.clamped
    assert verdict.resolved == 2.0


def test_clamp_clamps_above() -> None:
    verdict = clamp_speed(99.0, min_speed=0.1, max_speed=16.0)
    assert verdict.accepted
    assert verdict.clamped
    assert verdict.resolved == 16.0


def test_clamp_clamps_below() -> None:
    verdict = clamp_speed(0.001, min_speed=0.1, max_speed=16.0)
    assert verdict.accepted
    assert verdict.clamped
    assert verdict.resolved == 0.1


def test_clamp_rejects_non_finite() -> None:
    verdict = clamp_speed(math.inf, min_speed=0.1, max_speed=16.0)
    assert not verdict.accepted


def test_clamp_rejects_zero_and_negative() -> None:
    assert not clamp_speed(0, min_speed=0.1, max_speed=16.0).accepted
    assert not clamp_speed(-1, min_speed=0.1, max_speed=16.0).accepted


def test_profile_drops_out_of_range_presets() -> None:
    profile = build_speed_profile(
        presets=(0.001, 0.5, 1.0, 100.0),
        min_speed=0.1,
        max_speed=16.0,
        default_speed=1.0,
    )
    assert profile.presets == (0.5, 1.0)


def test_profile_dedupes_and_sorts() -> None:
    profile = build_speed_profile(
        presets=(2.0, 1.0, 2.0, 0.5),
        min_speed=0.1,
        max_speed=16.0,
        default_speed=1.0,
    )
    assert profile.presets == (0.5, 1.0, 2.0)


def test_next_and_previous_preset() -> None:
    profile = build_speed_profile(
        presets=(0.25, 0.5, 1.0, 2.0, 4.0),
        min_speed=0.1,
        max_speed=16.0,
        default_speed=1.0,
    )
    assert next_preset(profile, 1.0) == 2.0
    assert next_preset(profile, 4.0) == 4.0  # already at max
    assert previous_preset(profile, 1.0) == 0.5
    assert previous_preset(profile, 0.25) == 0.25  # already at min


def test_nearest_preset_snaps_to_closest() -> None:
    profile = build_speed_profile(
        presets=(0.25, 0.5, 1.0, 2.0, 4.0),
        min_speed=0.1,
        max_speed=16.0,
        default_speed=1.0,
    )
    assert nearest_preset(profile, 0.6) == 0.5
    assert nearest_preset(profile, 0.76) == 1.0
    assert nearest_preset(profile, 3.0) == 2.0  # tie goes lower
