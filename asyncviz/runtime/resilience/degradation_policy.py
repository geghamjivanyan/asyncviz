"""Maps subsystem health to a runtime :class:`EmergencyMode`.

Pure function — given a snapshot of breaker states, returns the
mode the runtime *should* be in. The manager calls this on every
state change + transitions the runtime accordingly. Keeping the
mapping pure means tests can drive it directly without booting a
manager.
"""

from __future__ import annotations

from collections.abc import Mapping

from asyncviz.runtime.resilience.isolation_configuration import EmergencyMode
from asyncviz.runtime.resilience.models.breaker_state import BreakerState
from asyncviz.runtime.resilience.models.subsystem_id import CRITICAL_SUBSYSTEMS


def derive_runtime_mode(
    *,
    states: Mapping[str, BreakerState],
    halt_on_critical: bool = False,
) -> EmergencyMode:
    """Compute the runtime mode from a per-subsystem breaker map."""
    if not states:
        return "normal"
    open_count = 0
    critical_open = False
    half_open_count = 0
    for name, state in states.items():
        if state == BreakerState.OPEN:
            open_count += 1
            if name in {s.value for s in CRITICAL_SUBSYSTEMS}:
                critical_open = True
        elif state == BreakerState.HALF_OPEN:
            half_open_count += 1
    if critical_open and halt_on_critical:
        return "halt"
    if critical_open:
        return "emergency"
    if open_count >= 2:
        return "shed"
    if open_count == 1 or half_open_count > 0:
        return "degraded"
    return "normal"
