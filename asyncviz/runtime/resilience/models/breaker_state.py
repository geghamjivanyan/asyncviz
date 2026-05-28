"""Circuit-breaker state machine."""

from __future__ import annotations

from enum import StrEnum


class BreakerState(StrEnum):
    CLOSED = "closed"
    """Healthy. Requests flow through normally."""

    OPEN = "open"
    """Tripped. Requests short-circuit immediately."""

    HALF_OPEN = "half_open"
    """Probing. A bounded number of requests are admitted to test
    whether the subsystem has recovered."""


def is_open(state: BreakerState) -> bool:
    return state == BreakerState.OPEN


def admits_traffic(state: BreakerState) -> bool:
    return state in (BreakerState.CLOSED, BreakerState.HALF_OPEN)
