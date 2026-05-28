"""Blocking-warning lifecycle states.

Each :class:`WarningGroup` (one per freeze window or out-of-window
bucket) walks through this state machine:

    OPENED → ESCALATING → ACTIVE → RECOVERED → EXPIRED

* **OPENED**     — first violation that crossed the policy threshold.
* **ESCALATING** — severity rose since the previous emission.
* **ACTIVE**     — additional violation observed at the same severity
  (refresh, no escalation).
* **RECOVERED**  — the originating freeze window closed cleanly, OR no
  new violations arrived within the recovery quiescence window.
* **EXPIRED**    — recovered group sat past its TTL without being
  re-opened. Expired groups are pruned from the active map but their
  RECOVERED/EXPIRED transition events stay in the replay log.

The terminal flag pair (``is_terminal`` + ``is_open``) lets consumers
filter / cap collection sizes without re-implementing the state-name
checks.

The :class:`BlockingWarningEmitterState` mirrors the engine lifecycle
states of every other monitoring engine in the runtime — orchestrators
read it the same way regardless of which engine they're watching.
"""

from __future__ import annotations

import threading
from enum import StrEnum


class BlockingWarningGroupState(StrEnum):
    """Per-group lifecycle states."""

    OPENED = "opened"
    ESCALATING = "escalating"
    ACTIVE = "active"
    RECOVERED = "recovered"
    EXPIRED = "expired"

    @property
    def is_open(self) -> bool:
        return self in (
            BlockingWarningGroupState.OPENED,
            BlockingWarningGroupState.ESCALATING,
            BlockingWarningGroupState.ACTIVE,
        )

    @property
    def is_terminal(self) -> bool:
        return self in (
            BlockingWarningGroupState.RECOVERED,
            BlockingWarningGroupState.EXPIRED,
        )


class BlockingWarningEmitterState(StrEnum):
    """Lifecycle states for the emitter engine itself."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class BlockingWarningEmitterLifecycle:
    """State guard for :class:`BlockingWarningEmitter`. Thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = BlockingWarningEmitterState.IDLE

    @property
    def state(self) -> BlockingWarningEmitterState:
        with self._lock:
            return self._state

    def mark(self, new: BlockingWarningEmitterState) -> BlockingWarningEmitterState:
        with self._lock:
            prev = self._state
            self._state = new
            return prev

    def is_running(self) -> bool:
        with self._lock:
            return self._state is BlockingWarningEmitterState.RUNNING

    def is_terminal(self) -> bool:
        with self._lock:
            return self._state in (
                BlockingWarningEmitterState.STOPPED,
                BlockingWarningEmitterState.FAILED,
            )
