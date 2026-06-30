"""Hysteresis helpers for the overload detector."""

from __future__ import annotations


def ema_smooth(previous: float, observation: float, *, decay: float) -> float:
    """Standard EMA: ``decay * previous + (1 - decay) * observation``.

    ``decay`` closer to 1.0 → slower adaptation.
    """
    if not (0.0 < decay < 1.0):
        raise ValueError("decay must be in (0, 1)")
    return decay * previous + (1.0 - decay) * observation


def needs_upgrade(current_ratio: float, threshold: float) -> bool:
    return current_ratio >= threshold


def needs_downgrade(
    current_ratio: float,
    lower_band: float,
    dwell_satisfied: bool,
) -> bool:
    """Downgrade only when *both* the lower band is satisfied and
    the dwell time has elapsed."""
    return current_ratio < lower_band and dwell_satisfied
