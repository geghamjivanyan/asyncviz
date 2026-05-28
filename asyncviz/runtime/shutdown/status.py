"""Canonical lifecycle states for the runtime shutdown coordinator.

The :class:`ShutdownPhase` is monotonic — every shutdown advances
through the phases in the order declared here, never backwards. The
order is part of the public protocol: orchestrators and dashboards
read the current phase to decide whether to retry, wait, or fail.
"""

from __future__ import annotations

from enum import StrEnum


class ShutdownPhase(StrEnum):
    """One step of the canonical shutdown sequence.

    * ``IDLE`` — coordinator hasn't been triggered; runtime is up.
    * ``DRAINING`` — websocket notify + queue drain in progress.
    * ``FINALIZING`` — replay checkpoint + final snapshot in progress.
    * ``STOPPING`` — services + subscriptions being torn down.
    * ``STOPPED`` — clean shutdown complete; report available.
    * ``FAILED`` — shutdown encountered an unrecoverable error before
      reaching ``STOPPED``. Report is still available; it carries the
      failure metadata.

    The wire string values are stable; coordinate with the TypeScript
    ``ShutdownPhase`` type before changing them.
    """

    IDLE = "idle"
    DRAINING = "draining"
    FINALIZING = "finalizing"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


#: Monotonic ordering — higher index means later in the sequence.
_PHASE_ORDER: dict[ShutdownPhase, int] = {
    ShutdownPhase.IDLE: 0,
    ShutdownPhase.DRAINING: 1,
    ShutdownPhase.FINALIZING: 2,
    ShutdownPhase.STOPPING: 3,
    ShutdownPhase.STOPPED: 4,
    ShutdownPhase.FAILED: 5,
}


def phase_index(phase: ShutdownPhase) -> int:
    """Numeric index for ordering."""
    return _PHASE_ORDER[phase]


def is_terminal(phase: ShutdownPhase) -> bool:
    """Whether ``phase`` is a final state (no further transitions)."""
    return phase in {ShutdownPhase.STOPPED, ShutdownPhase.FAILED}


def is_in_progress(phase: ShutdownPhase) -> bool:
    """Whether the coordinator is mid-shutdown but not yet finished."""
    return phase in {
        ShutdownPhase.DRAINING,
        ShutdownPhase.FINALIZING,
        ShutdownPhase.STOPPING,
    }
