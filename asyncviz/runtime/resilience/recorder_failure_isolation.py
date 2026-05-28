"""Recorder-subsystem failure isolation adapter.

Recorder failures (disk full, archive corruption, serialization
errors) need different handling from the streaming subsystems —
data loss is the worst possible outcome, so the adapter records
*explicit data-loss markers* the operator can see in diagnostics
instead of silently dropping events.
"""

from __future__ import annotations

import threading

from asyncviz.runtime.resilience.failure_domain import FailureDomain
from asyncviz.runtime.resilience.subsystem_boundary import (
    AsyncSubsystemBoundary,
    SubsystemBoundary,
)


class RecorderFailureIsolation:
    __slots__ = ("_data_loss_events", "_domain", "_lock")

    def __init__(self, domain: FailureDomain) -> None:
        self._domain = domain
        self._lock = threading.Lock()
        self._data_loss_events = 0

    def isolate_write(
        self,
        *,
        payload_kind: str,
        suppress: bool = True,
    ) -> SubsystemBoundary:
        return SubsystemBoundary(
            self._domain,
            payload_kind=payload_kind,
            suppress=suppress,
            on_failure=self._note_data_loss,
            swallow_unavailable=True,
        )

    def isolate_flush(
        self,
        *,
        suppress: bool = False,
    ) -> AsyncSubsystemBoundary:
        return AsyncSubsystemBoundary(
            self._domain,
            payload_kind="",
            suppress=suppress,
            on_failure=self._note_data_loss,
            swallow_unavailable=False,
        )

    def data_loss_events(self) -> int:
        with self._lock:
            return self._data_loss_events

    def reset_data_loss(self) -> None:
        with self._lock:
            self._data_loss_events = 0

    def _note_data_loss(self, _event: object) -> None:
        with self._lock:
            self._data_loss_events += 1
