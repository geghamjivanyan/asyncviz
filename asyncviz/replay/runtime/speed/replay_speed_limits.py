"""Speed clamping + validation helpers.

Centralizes the rules so the controller, dispatch, and limits-check
code paths all agree on what "valid" means. Returns structured
verdicts instead of booleans so callers can preserve the original
request alongside the clamp decision.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClampVerdict:
    """Result of validating + clamping one speed value."""

    accepted: bool
    """False when the value was NaN / ≤0 / non-finite."""

    clamped: bool
    """True when the value was finite but out of range and got
    normalized to ``min_speed`` or ``max_speed``."""

    requested: float
    resolved: float
    reason: str = ""


def clamp_speed(
    requested: float,
    *,
    min_speed: float,
    max_speed: float,
) -> ClampVerdict:
    """Validate + clamp ``requested``."""
    if not isinstance(requested, (int, float)):
        return ClampVerdict(
            accepted=False,
            clamped=False,
            requested=float("nan"),
            resolved=float("nan"),
            reason=f"non-numeric speed value: {type(requested).__name__}",
        )
    value = float(requested)
    if math.isnan(value) or math.isinf(value):
        return ClampVerdict(
            accepted=False,
            clamped=False,
            requested=value,
            resolved=float("nan"),
            reason="non-finite speed",
        )
    if value <= 0:
        return ClampVerdict(
            accepted=False,
            clamped=False,
            requested=value,
            resolved=float("nan"),
            reason="speed must be > 0",
        )
    if value < min_speed:
        return ClampVerdict(
            accepted=True,
            clamped=True,
            requested=value,
            resolved=min_speed,
            reason=f"clamped to min_speed={min_speed}",
        )
    if value > max_speed:
        return ClampVerdict(
            accepted=True,
            clamped=True,
            requested=value,
            resolved=max_speed,
            reason=f"clamped to max_speed={max_speed}",
        )
    return ClampVerdict(
        accepted=True,
        clamped=False,
        requested=value,
        resolved=value,
    )
