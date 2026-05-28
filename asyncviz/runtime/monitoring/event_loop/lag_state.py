"""Lag-monitor lifecycle state machine.

Mirrors the runtime's other lifecycle enums (``RuntimeState``,
``ShutdownPhase``) so the dashboard's health probes can speak about the
monitor with the same vocabulary.

State transitions::

    IDLE → STARTING → RUNNING → STOPPING → STOPPED
                          ↓
                       FAILED

The monitor enforces ordering — see :class:`LagMonitorLifecycle` — so
double-starts / double-stops are no-ops and a stop from STARTING
unwinds cleanly without ever exposing the loop to a half-built state.
"""

from __future__ import annotations

import threading
from enum import StrEnum


class LagMonitorState(StrEnum):
    """Lifecycle states for the lag monitor."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class LagMonitorLifecycle:
    """State guard for :class:`EventLoopLagMonitor`.

    All transitions go through here so the monitor's public surface
    (``start`` / ``stop`` / ``is_running``) reads only the current
    state and never special-cases internal booleans. Returning the
    *previous* state from :meth:`mark` lets callers decide what to do
    when the transition is a no-op.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = LagMonitorState.IDLE

    @property
    def state(self) -> LagMonitorState:
        with self._lock:
            return self._state

    def mark(self, new: LagMonitorState) -> LagMonitorState:
        """Set state and return the previous value."""
        with self._lock:
            prev = self._state
            self._state = new
            return prev

    def is_running(self) -> bool:
        with self._lock:
            return self._state is LagMonitorState.RUNNING

    def is_terminal(self) -> bool:
        with self._lock:
            return self._state in (LagMonitorState.STOPPED, LagMonitorState.FAILED)
