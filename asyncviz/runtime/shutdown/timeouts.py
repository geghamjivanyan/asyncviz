"""Per-step timeout policy for the shutdown coordinator.

Each step has its own ceiling. The coordinator never blocks forever:
when a step hits its timeout, the coordinator records the event in
the :class:`ShutdownReport`, escalates (forced disconnect / forced
cancellation as appropriate), and continues to the next phase.

Defaults are tuned for the embedded-dashboard use case — a single
process, a handful of clients, replay buffers in the kilobytes range.
Deployments with bigger fan-out or larger retention windows can pass
a custom :class:`ShutdownTimeouts` to the coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShutdownTimeouts:
    """Bounds on each step of the shutdown sequence.

    Values are in seconds. ``None`` means no bound — generally a bad
    idea in production, but useful for tests that want to observe
    the natural drain time.
    """

    #: Time given to broadcast the ``system_status="shutting_down"``
    #: envelope and let connected clients read it before the gateway
    #: starts closing sockets. Should be < total drain budget.
    notification_window_seconds: float = 0.25

    #: Maximum time spent waiting for the event queue + bus + bridge
    #: to drain in-flight events. Bounded so a stuck consumer can't
    #: hold the whole shutdown.
    drain_seconds: float = 2.0

    #: Maximum time the replay buffer + snapshot service have to
    #: finalize. They're synchronous today; the bound exists to catch
    #: future regressions.
    finalize_seconds: float = 2.0

    #: Maximum time service ``.stop()`` calls have combined. Hitting
    #: this triggers a forced-disconnect escalation in the report.
    stop_seconds: float = 3.0

    #: Total cap across every step. Acts as a safety net — even if a
    #: per-step timeout fires, the coordinator must return inside this
    #: window. ``None`` disables the cap.
    total_seconds: float | None = 10.0
