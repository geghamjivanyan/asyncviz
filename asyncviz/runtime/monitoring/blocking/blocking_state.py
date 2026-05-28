"""Blocking detector lifecycle states.

Mirrors :class:`LagMonitorState` so dashboards / health probes can talk
about the detector with the same vocabulary they use for the lag
monitor. The detector itself is largely passive (it reacts to lag
measurements) but it still owns a small amount of long-lived state —
escalation counters, open windows, cooldown tables — that needs a
controlled startup/shutdown sequence so test teardown and shutdown
coordination are deterministic.
"""

from __future__ import annotations

import threading
from enum import StrEnum


class BlockingDetectorState(StrEnum):
    """Lifecycle states for :class:`BlockingThresholdDetector`."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class BlockingDetectorLifecycle:
    """State guard. Mirrors :class:`LagMonitorLifecycle`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = BlockingDetectorState.IDLE

    @property
    def state(self) -> BlockingDetectorState:
        with self._lock:
            return self._state

    def mark(self, new: BlockingDetectorState) -> BlockingDetectorState:
        with self._lock:
            prev = self._state
            self._state = new
            return prev

    def is_running(self) -> bool:
        with self._lock:
            return self._state is BlockingDetectorState.RUNNING

    def is_terminal(self) -> bool:
        with self._lock:
            return self._state in (
                BlockingDetectorState.STOPPED,
                BlockingDetectorState.FAILED,
            )
